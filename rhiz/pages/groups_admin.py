"""Admin page: moderate ALL groups system-wide (/groups).

Admin-only. Lists every group (across all users) with its share link + QR,
and lets an admin open/close or delete any of them — e.g. on behalf of other
users once group creation is extended beyond admins. Groups are created from
the Your Groups page, not here.
"""

import reflex as rx
from sqlmodel import select

from rhiz.state.base import AppState, Group, GroupStatus, UserTypes, User
from rhiz.utils.groups import set_group_status, set_group_public, delete_group
from rhiz.utils.qr import qr_data_uri
from rhiz.styles import page_params
from rhiz.components import container, navbar
from rhiz.pages.group_common import public_base_url, group_row


class GroupsAdminState(AppState):
    rows: list[dict] = []

    @rx.var
    def is_admin(self) -> bool:
        return self.user is not None and self.user.role == UserTypes.admin

    def on_load(self):
        result = self.check_login()
        if result:
            return result
        self._refresh()

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


def groups_admin_page():
    return container(
        navbar(),
        rx.cond(
            GroupsAdminState.is_admin,
            rx.vstack(
                rx.heading("All Groups", size="6"),
                rx.text(
                    "Every group on the site. Open/close or delete any of them "
                    "— including on behalf of other users.",
                    size="2",
                ),
                rx.cond(
                    GroupsAdminState.rows.length() == 0,
                    rx.callout("No groups have been created yet.", size="1"),
                    rx.fragment(),
                ),
                rx.foreach(
                    GroupsAdminState.rows,
                    lambda r: group_row(GroupsAdminState, r),
                ),
                spacing="4",
                align="stretch",
                width="100%",
                padding="24px",
            ),
            rx.center(
                rx.text("This page is for administrators only."),
                min_height="50vh",
            ),
        ),
    )


@rx.page(route="/groups", on_load=GroupsAdminState.on_load, **page_params)
def groups_admin():
    """Admin-only: moderate all groups."""
    return groups_admin_page()
