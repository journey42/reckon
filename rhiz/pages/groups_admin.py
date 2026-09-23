"""Admin page: moderate ALL groups system-wide (/groups).

Admin-only. Lists every group (across all users) with its share link + QR,
and lets an admin open/close or delete any of them — e.g. on behalf of other
users once group creation is extended beyond admins. Groups are created from
the Your Groups page, not here.

Also provides member management: add/remove members by email and view
member lists per group.
"""

import reflex as rx
from sqlmodel import select

from rhiz.state.base import (
    AppState,
    Group,
    GroupStatus,
    ReckoningTypes,
    UserTypes,
    User,
)
from rhiz.utils.groups import (
    set_group_status,
    set_group_public,
    delete_group,
    add_member_by_email,
    get_group_members,
    remove_member,
)
from rhiz.utils.qr import qr_data_uri
from rhiz.styles import page_params, button_style, input_style
from rhiz.components import container, navbar
from rhiz.pages.group_common import public_base_url, group_row


class GroupsAdminState(AppState):
    rows: list[dict] = []

    # Activity feed: counts + timestamps only — never group content. This is
    # the client's visibility requirement: see groups being created, members
    # joining, and posting volume, without seeing what anyone posted.
    activity: list[dict] = []
    post_stats: list[dict] = []
    invite_funnel: list[dict] = []

    # Member management state
    selected_group_id: int = 0
    members: list[dict] = []
    add_member_email: str = ""
    add_member_message: str = ""

    @rx.var
    def is_admin(self) -> bool:
        return self.user is not None and self.user.role == UserTypes.admin

    def on_load(self):
        result = self.check_login()
        if result:
            return result
        self._refresh()
        self._load_activity()
        self._load_invite_funnel()

    def _refresh(self):
        self.rows = []
        if not (self.user and self.user.role == UserTypes.admin):
            return
        base = public_base_url()
        with rx.session() as session:
            # Single outer join so each group's creator username comes back in
            # one query (no per-row lookup against the remote DB).
            rows = session.exec(
                select(Group, User.username)
                .outerjoin(User, User.id == Group.created_by)
                # Live Q&A rooms have their own dashboard (/live, /live/all);
                # they are groups internally but must not clutter this page.
                .where(Group.is_room == False)  # noqa: E712
                .order_by(Group.created_at.desc())
            ).all()
            for g, creator_username in rows:
                url = f"{base}/group/{g.slug}"
                self.rows.append(
                    {
                        "id": g.id,
                        "slug": g.slug,
                        "name": g.name,
                        "status": g.status,
                        "is_public": g.is_public,
                        "url": url,
                        "qr": qr_data_uri(url),
                        "creator": creator_username or "Unknown",
                        "is_owner": True,
                    }
                )

    # ── Activity panel (counts + timestamps only) ────────────────────

    def _load_activity(self):
        """Recent group lifecycle events: created / joined / posted.

        Counts and timestamps only — no post content is selected. Sources:
        the `log` table (created group, joined group) and per-group reckoning
        counts (posts), which reveal volume but never content.
        """
        from datetime import datetime, timezone
        from sqlalchemy import func as sa_func
        from rhiz.state.base import Log, Reckoning

        self.activity = []
        if not (self.user and self.user.role == UserTypes.admin):
            return
        with rx.session() as session:
            # Per-group post counts + latest post timestamp (volume only).
            post_stats = session.exec(
                select(
                    Reckoning.group_id,
                    sa_func.count(Reckoning.id),
                    sa_func.max(Reckoning.created_at),
                )
                .where(Reckoning.type == ReckoningTypes.concept)
                .group_by(Reckoning.group_id)
            ).all()
            post_counts = {
                gid: {"posts": n, "last_post": ts} for gid, n, ts in post_stats
            }

            # Groups with names, for readable rows.
            groups = {
                g.id: g.name
                for g in session.exec(
                    select(Group).where(Group.is_room == False)  # noqa: E712
                ).all()
            }

            # Lifecycle events from the audit log, newest first.
            logs = session.exec(
                select(Log)
                .where(
                    Log.type.in_(["group", "group_join", "user"])
                    & Log.content.contains("group")
                )
                .order_by(Log.created_at.desc())
                .limit(60)
            ).all()
            usernames = {
                u.id: u.username
                for u in session.exec(select(User)).all()
            }
            for entry in logs:
                kind = (
                    "created"
                    if entry.type == "group"
                    else ("joined" if entry.type == "group_join" else None)
                )
                if kind is None:
                    continue
                # Parse group id from the log content ("created group X" /
                # "joined group N").
                gid = None
                try:
                    gid = int(entry.content.rsplit(" ", 1)[-1])
                except (ValueError, IndexError):
                    pass
                self.activity.append(
                    {
                        "when": entry.created_at.strftime("%b %d %H:%M UTC"),
                        "who": usernames.get(entry.user_id, "unknown"),
                        "kind": kind,
                        "group": groups.get(gid, f"#{gid}" if gid else "?"),
                    }
                )

            # Post-volume rows per group (content-never-selected).
            self.post_stats = [
                {
                    "group": groups.get(gid, f"#{gid}"),
                    "posts": stats["posts"],
                    "last_post": (
                        stats["last_post"].strftime("%b %d %H:%M UTC")
                        if stats["last_post"]
                        else "never"
                    ),
                }
                for gid, stats in sorted(
                    post_counts.items(),
                    key=lambda kv: kv[1]["last_post"] or datetime.min.replace(
                        tzinfo=None
                    ),
                    reverse=True,
                )
                if gid in groups
            ]

    def _load_invite_funnel(self):
        """Signups that started from a group invite link — did they succeed?

        signup_group_slug records the origin group; enabled records whether
        the signup completed. Group contents are never touched.
        """
        self.invite_funnel = []
        if not (self.user and self.user.role == UserTypes.admin):
            return
        from sqlalchemy import case, func as sa_func

        with rx.session() as session:
            rows = session.exec(
                select(
                    User.signup_group_slug,
                    sa_func.count(User.id),
                    sa_func.sum(
                        case((User.enabled == True, 1), else_=0)  # noqa: E712
                    ),
                )
                .where(User.signup_group_slug != "")
                .group_by(User.signup_group_slug)
            ).all()
            for slug, total, enabled_count in rows:
                self.invite_funnel.append(
                    {
                        "group": slug,
                        "signups": total,
                        "joined": enabled_count or 0,
                    }
                )

    def toggle_status(self, group_id: int, current: str):
        if not (self.user and self.user.role == UserTypes.admin):
            return
        new_status = (
            GroupStatus.closed if current == GroupStatus.open else GroupStatus.open
        )
        with rx.session() as session:
            set_group_status(session, group_id, new_status)
        self._refresh()

    def delete_group(self, group_id: int):
        if not (self.user and self.user.role == UserTypes.admin):
            return
        with rx.session() as session:
            delete_group(session, group_id)  # admin: delete any group
        self._refresh()

    def toggle_public(self, group_id: int):
        if not (self.user and self.user.role == UserTypes.admin):
            return
        with rx.session() as session:
            group = session.exec(select(Group).where(Group.id == group_id)).first()
            if group is not None:
                set_group_public(session, group_id, not group.is_public)
        self._refresh()

    # ── Member management ────────────────────────────────────────────

    def load_members(self, group_id: int):
        """Load the member list for a specific group."""
        self.selected_group_id = group_id
        self.add_member_email = ""
        self.add_member_message = ""
        with rx.session() as session:
            self.members = get_group_members(session, group_id)

    def close_member_panel(self):
        """Close the member panel without hitting the database."""
        self.selected_group_id = 0
        self.members = []
        self.add_member_email = ""
        self.add_member_message = ""

    @rx.event
    def set_add_member_email(self, value: str):
        self.add_member_email = value or ""

    def add_member(self):
        """Add a member to the selected group by email."""
        if not self.add_member_email.strip():
            self.add_member_message = "Please enter an email address."
            return
        added_username = None
        with rx.session() as session:
            result = add_member_by_email(
                session, self.add_member_email.strip().lower(), self.selected_group_id
            )
            if result:
                # Fetch username inside the session to avoid detached instance access
                user = session.exec(select(User).where(User.id == result.user_id)).first()
                added_username = user.username if user else f"user {result.user_id}"
        if added_username:
            self.add_member_message = f"Added {added_username} to group."
            self.load_members(self.selected_group_id)
        else:
            self.add_member_message = f"No user found with email '{self.add_member_email}'."

    def remove_member_handler(self, member_id: int):
        """Remove a member from the selected group."""
        with rx.session() as session:
            removed = remove_member(session, member_id)
        if removed:
            self.load_members(self.selected_group_id)
        else:
            self.add_member_message = "Failed to remove member."


def _member_panel():
    """Collapsible member management panel for the selected group."""
    return rx.cond(
        GroupsAdminState.selected_group_id > 0,
        rx.card(
            rx.vstack(
                rx.heading("Manage Members", size="4"),
                # Add member form
                rx.flex(
                    rx.input(
                        placeholder="Email address",
                        on_blur=GroupsAdminState.set_add_member_email,
                        name="member_email",
                        **input_style,
                    ),
                    rx.button(
                        "Add to Group",
                        on_click=GroupsAdminState.add_member,
                        variant="solid",
                        size="2",
                    ),
                    direction="row",
                    align="center",
                    gap="8px",
                    width="100%",
                ),
                rx.cond(
                    GroupsAdminState.add_member_message != "",
                    rx.callout(
                        GroupsAdminState.add_member_message,
                        size="1",
                        color_scheme=rx.cond(
                            GroupsAdminState.add_member_message.startswith("Added"),
                            "green",
                            "red",
                        ),
                    ),
                    rx.fragment(),
                ),
                # Member list
                rx.text(f"Members ({GroupsAdminState.members.length()})", size="2"),
                rx.cond(
                    GroupsAdminState.members.length() == 0,
                    rx.text("No members yet.", size="1", color="gray"),
                    rx.foreach(
                        GroupsAdminState.members,
                        lambda m: rx.flex(
                            rx.vstack(
                                rx.text(m["username"], weight="medium"),
                                rx.text(m["email"], size="1", color="gray"),
                                align="start",
                                spacing="0",
                                flex_grow="1",
                            ),
                            rx.button(
                                "Remove",
                                on_click=GroupsAdminState.remove_member_handler(m["id"]),
                                color_scheme="red",
                                variant="soft",
                                size="1",
                            ),
                            direction="row",
                            align="center",
                            width="100%",
                            gap="8px",
                        ),
                    ),
                ),
                rx.button(
                    "Close",
                    on_click=GroupsAdminState.close_member_panel(),
                    variant="soft",
                    color_scheme="gray",
                    size="1",
                ),
                spacing="3",
                width="100%",
            ),
            width="400px",
        ),
        rx.fragment(),
    )


def _activity_panel() -> rx.Component:
    """Counts + timestamps of group lifecycle activity — never content."""
    return rx.vstack(
        rx.heading("Recent activity", size="5"),
        rx.text(
            "Groups created, members joined, and posting volume — counts and "
            "timestamps only. Group contents stay private to their groups.",
            size="2",
            color_scheme="gray",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("When"),
                    rx.table.column_header_cell("Who"),
                    rx.table.column_header_cell("Event"),
                    rx.table.column_header_cell("Group"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    GroupsAdminState.activity,
                    lambda a: rx.table.row(
                        rx.table.cell(a["when"]),
                        rx.table.cell(a["who"]),
                        rx.table.cell(
                            rx.badge(
                                a["kind"],
                                color_scheme=rx.cond(
                                    a["kind"] == "created", "blue", "green"
                                ),
                                variant="soft",
                            ),
                        ),
                        rx.table.cell(a["group"]),
                    ),
                )
            ),
            size="1",
            width="100%",
        ),
        rx.heading("Posting volume by group", size="4"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Group"),
                    rx.table.column_header_cell("Posts"),
                    rx.table.column_header_cell("Last post"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    GroupsAdminState.post_stats,
                    lambda p: rx.table.row(
                        rx.table.cell(p["group"]),
                        rx.table.cell(p["posts"]),
                        rx.table.cell(p["last_post"]),
                    ),
                )
            ),
            size="1",
            width="100%",
        ),
        rx.heading("Invite-link signups", size="4"),
        rx.text(
            "Signups that started from a group's invite link, and how many "
            "of those accounts are active members.",
            size="2",
            color_scheme="gray",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Group"),
                    rx.table.column_header_cell("Signups via link"),
                    rx.table.column_header_cell("Joined"),
                )
            ),
            rx.table.body(
                rx.cond(
                    GroupsAdminState.invite_funnel.length() == 0,
                    rx.table.row(
                        rx.table.cell(
                            "No signups have come through invite links yet.",
                            colspan="3",
                        ),
                    ),
                    rx.foreach(
                        GroupsAdminState.invite_funnel,
                        lambda f: rx.table.row(
                            rx.table.cell(f["group"]),
                            rx.table.cell(f["signups"]),
                            rx.table.cell(f["joined"]),
                        ),
                    ),
                )
            ),
            size="1",
            width="100%",
        ),
        spacing="3",
        align="stretch",
        width="100%",
    )


def groups_admin_page():
    return container(
        navbar(),
        rx.cond(
            GroupsAdminState.is_admin,
            rx.flex(
                # Main content: group list
                rx.vstack(
                    rx.heading("All Groups", size="6"),
                    rx.text(
                        "Every group on the site. Open/close or delete any of them "
                        "— including on behalf of other users. Click 'Members' on "
                        "any group to manage its membership.",
                        size="2",
                    ),
                    rx.cond(
                        GroupsAdminState.rows.length() == 0,
                        rx.callout("No groups have been created yet.", size="1"),
                        rx.fragment(),
                    ),
                    rx.foreach(
                        GroupsAdminState.rows,
                        lambda r: _group_row_with_members(GroupsAdminState, r),
                    ),
                    _activity_panel(),
                    spacing="4",
                    align="stretch",
                    width="100%",
                    flex_grow="1",
                ),
                # Side panel: member management
                rx.box(_member_panel()),
                spacing="4",
                width="100%",
                padding="24px",
            ),
            rx.center(
                rx.text("This page is for administrators only."),
                min_height="50vh",
            ),
        ),
    )


def _group_row_with_members(state_cls, r):
    """A group card with an additional 'Members' button."""
    return rx.card(
        rx.flex(
            rx.vstack(
                rx.heading(r["name"], size="3"),
                rx.link(
                    r["url"],
                    href=r["url"],
                    size="1",
                    width="100%",
                    style={"wordBreak": "break-all"},
                ),
                rx.text("Status: ", r["status"], size="1"),
                rx.cond(
                    r["creator"] != "",
                    rx.text("Created by: ", r["creator"], size="1", color="gray"),
                    rx.fragment(),
                ),
                align="start",
                spacing="1",
                flex_grow="1",
                min_width="0",
            ),
            rx.image(src=r["qr"], width="96px", height="96px", flex_shrink="0"),
            rx.vstack(
                # Owner-only controls
                rx.cond(
                    r["is_owner"],
                    rx.fragment(
                        rx.button(
                            rx.cond(r["status"] == GroupStatus.open, "Close", "Reopen"),
                            on_click=state_cls.toggle_status(r["id"], r["status"]),
                            variant="soft",
                            size="1",
                        ),
                        rx.button(
                            rx.cond(r["is_public"], "Ungraduate", "Graduate"),
                            on_click=state_cls.toggle_public(r["id"]),
                            variant="soft",
                            color_scheme=rx.cond(r["is_public"], "green", "gray"),
                            size="1",
                        ),
                        rx.button(
                            "Delete",
                            on_click=state_cls.delete_group(r["id"]),
                            color_scheme="red",
                            variant="soft",
                            size="1",
                        ),
                    ),
                    rx.fragment(),
                ),
                # Member management button (always visible for admins)
                rx.button(
                    "Members",
                    on_click=state_cls.load_members(r["id"]),
                    variant="solid",
                    color_scheme="blue",
                    size="1",
                ),
                spacing="2",
                flex_shrink="0",
            ),
            direction="row",
            align="center",
            wrap="wrap",
            gap="12px",
            width="100%",
        ),
        width="100%",
    )


@rx.page(route="/groups", on_load=GroupsAdminState.on_load, **page_params)
def groups_admin():
    """Admin-only: moderate all groups."""
    return groups_admin_page()
