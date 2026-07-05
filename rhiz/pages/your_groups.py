"""Per-user page: the current user's own groups (/your_groups).

Visible to anyone entitled to create groups (GROUP_CREATE_MIN_ROLE). Lists
only the groups this user created, with share link + QR, and lets them
open/close or delete their own. Site-wide moderation lives on the admin-only
/groups page.
"""

import reflex as rx
from sqlmodel import select

from rhiz.state.base import AppState, Group, GroupStatus
from rhiz.utils.groups import set_group_status, delete_group
from rhiz.utils.permissions import can_manage_groups
from rhiz.utils.qr import qr_data_uri
from rhiz.styles import page_params
from rhiz.components import container, navbar
from rhiz.pages.group_common import public_base_url, group_row


class YourGroupsState(AppState):
    rows: list[dict] = []

    @rx.var
    def can_manage(self) -> bool:
        return can_manage_groups(self.user)

    def on_load(self):
        result = self.check_login()
        if result:
            return result
        self._refresh()

    def _refresh(self):
        self.rows = []
        if not can_manage_groups(self.user):
            return
        base = public_base_url()
        with rx.session() as session:
            groups = session.exec(
                select(Group)
                .where(Group.created_by == self.user.id)
                .order_by(Group.created_at.desc())
            ).all()
            for g in groups:
                url = f"{base}/group/{g.slug}"
                self.rows.append(
                    {
                        "id": g.id,
                        "slug": g.slug,
                        "name": g.name,
                        "status": g.status,
                        "url": url,
                        "qr": qr_data_uri(url),
                        "creator": "",  # own page — creator line stays hidden
                    }
                )

    def toggle_status(self, group_id: int, current: str):
        if not can_manage_groups(self.user):
            return
        new_status = (
            GroupStatus.closed
            if current == GroupStatus.open
            else GroupStatus.open
        )
        with rx.session() as session:
            # owner_id guard: only act on the user's own group
            group = session.exec(
                select(Group).where(Group.id == group_id)
            ).first()
            if group is not None and group.created_by == self.user.id:
                set_group_status(session, group_id, new_status)
        self._refresh()

    def delete_group(self, group_id: int):
        if not can_manage_groups(self.user):
            return
        with rx.session() as session:
            delete_group(session, group_id, owner_id=self.user.id)
        self._refresh()


def your_groups_page():
    return container(
        navbar(),
        rx.cond(
            YourGroupsState.can_manage,
            rx.vstack(
                rx.heading("Your Groups", size="6"),
                rx.text(
                    "Groups you've created. Share the link or QR code, and "
                    "open/close or delete them here.",
                    size="2",
                ),
                rx.cond(
                    YourGroupsState.rows.length() == 0,
                    rx.callout(
                        "You haven't created any groups yet. Click \"Create "
                        "Group\" to get started.",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                rx.foreach(
                    YourGroupsState.rows,
                    lambda r: group_row(YourGroupsState, r),
                ),
                spacing="4",
                align="stretch",
                width="100%",
                padding="24px",
            ),
            rx.center(
                rx.text("You do not have access to groups."),
                min_height="50vh",
            ),
        ),
    )


@rx.page(route="/your_groups", on_load=YourGroupsState.on_load, **page_params)
def your_groups():
    """The current user's own groups."""
    return your_groups_page()
