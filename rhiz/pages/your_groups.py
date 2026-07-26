"""Per-user page: the current user's own groups (/your_groups).

Visible to anyone entitled to create groups (GROUP_CREATE_MIN_ROLE). Lists
only the groups this user created, with share link + QR, and lets them
open/close or delete their own. Site-wide moderation lives on the admin-only
/groups page.

Also shows groups the user has explicitly joined (via GroupMember) and
groups they've participated in through content submission.
"""

import reflex as rx
from sqlmodel import select

from rhiz.state.base import AppState, Group, GroupStatus
from rhiz.utils.groups import set_group_status, set_group_public, delete_group
from rhiz.utils.permissions import can_manage_groups
from rhiz.utils.qr import qr_data_uri
from rhiz.styles import page_params
from rhiz.components import container, navbar
from rhiz.pages.group_common import public_base_url, group_row
from rhiz.components.group_dialog import group_dialog, GroupDialogState
from rhiz.components.buttons import create_group_button


class YourGroupsState(AppState):
    rows: list[dict] = []

    @rx.var
    def can_manage(self) -> bool:
        return can_manage_groups(self.user)

    def on_load(self):
        result = self.check_user_enabled()
        if result:
            return result
        result = self.check_login()
        if result:
            return result
        self._refresh()

    def _refresh(self):
        self.rows = []
        base = public_base_url()
        seen_ids = set()

        def _add_group(g):
            """Add a group to the list if not already present."""
            if g.id in seen_ids:
                return
            seen_ids.add(g.id)
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
                    "creator": "",
                    "is_owner": g.created_by == self.user.id
                        or (self.user and self.user.role >= 2),
                }
            )

        with rx.session() as session:
            # 1. Groups the user created (only if they can create groups)
            if can_manage_groups(self.user):
                created = session.exec(
                    select(Group)
                    .where(Group.created_by == self.user.id)
                    .order_by(Group.created_at.desc())
                ).all()
                for g in created:
                    _add_group(g)

            # 2. Groups the user is explicitly a member of (via GroupMember)
            from rhiz.state.base import GroupMember
            memberships = session.exec(
                select(GroupMember)
                .where(GroupMember.user_id == self.user.id)
                .order_by(GroupMember.joined_at.desc())
            ).all()
            for m in memberships:
                g = session.exec(select(Group).where(Group.id == m.group_id)).first()
                if g:
                    _add_group(g)

            # 3. Groups the user has participated in (via reckonings with group_id)
            #    — legacy fallback for users who interacted before membership tracking
            from rhiz.state.base import Reckoning
            from sqlalchemy import distinct
            participated_ids = session.exec(
                select(distinct(Reckoning.group_id))
                .where(
                    Reckoning.user_id == self.user.id,
                    Reckoning.group_id.isnot(None),
                )
            ).all()
            for gid in participated_ids:
                if gid in seen_ids:
                    continue
                g = session.exec(select(Group).where(Group.id == gid)).first()
                if g:
                    _add_group(g)

            # 4. Group the user signed up from (if not already shown above)
            signup_slug = getattr(self.user, "signup_group_slug", None)
            if signup_slug:
                affinity = session.exec(
                    select(Group).where(Group.slug == signup_slug)
                ).first()
                if affinity:
                    _add_group(affinity)

    def toggle_status(self, group_id: int, current: str):
        if not can_manage_groups(self.user):
            return
        new_status = (
            GroupStatus.closed if current == GroupStatus.open else GroupStatus.open
        )
        with rx.session() as session:
            # owner_id guard: only act on the user's own group
            group = session.exec(select(Group).where(Group.id == group_id)).first()
            if group is not None and group.created_by == self.user.id:
                set_group_status(session, group_id, new_status)
        self._refresh()

    def delete_group(self, group_id: int):
        if not can_manage_groups(self.user):
            return
        with rx.session() as session:
            delete_group(session, group_id, owner_id=self.user.id)
        self._refresh()

    def toggle_public(self, group_id: int):
        if not can_manage_groups(self.user):
            return
        with rx.session() as session:
            group = session.exec(select(Group).where(Group.id == group_id)).first()
            if group is not None and group.created_by == self.user.id:
                set_group_public(session, group_id, not group.is_public)
        self._refresh()


def your_groups_page():
    return container(
        navbar(),
        rx.vstack(
            rx.hstack(
                rx.heading("Your Groups", size="6"),
                rx.spacer(),
                rx.cond(
                    YourGroupsState.can_manage,
                    create_group_button(
                        on_click=GroupDialogState.open,
                    ),
                    rx.fragment(),
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                "Groups you've created or joined. Share the link or QR code, "
                "and open/close or delete them here.",
                size="2",
            ),
            rx.cond(
                YourGroupsState.rows.length() == 0,
                rx.callout(
                    "You haven't joined any groups yet.",
                    size="1",
                ),
                rx.fragment(),
            ),
            rx.foreach(
                YourGroupsState.rows,
                lambda r: group_row(YourGroupsState, r),
            ),
            group_dialog(),
            spacing="4",
            align="stretch",
            width="100%",
            padding="24px",
        ),
    )


@rx.page(route="/your_groups", on_load=YourGroupsState.on_load, **page_params)
def your_groups():
    """The current user's own groups."""
    return your_groups_page()
