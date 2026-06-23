"""Admin page: moderate ALL debates system-wide (/debates).

Admin-only. Lists every debate (across all users) with its share link + QR,
and lets an admin open/close or delete any of them — e.g. on behalf of other
users once debate creation is extended beyond admins. Debates are created from
the "Create Debate" action in a concept's card menu, not here.
"""

import reflex as rx
from sqlmodel import select

from rhiz.state.base import AppState, Debate, DebateStatus, UserTypes
from rhiz.utils.debates import set_debate_status, delete_debate
from rhiz.utils.qr import qr_data_uri
from rhiz.styles import page_params
from rhiz.components import container, navbar
from rhiz.pages.debate_common import public_base_url, debate_row


class DebatesAdminState(AppState):
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
            debates = session.exec(
                select(Debate).order_by(Debate.created_at.desc())
            ).all()
            for d in debates:
                url = f"{base}/debate/{d.slug}"
                self.rows.append(
                    {
                        "id": d.id,
                        "slug": d.slug,
                        "title": d.title,
                        "status": d.status,
                        "url": url,
                        "qr": qr_data_uri(url),
                    }
                )

    def toggle_status(self, debate_id: int, current: str):
        if not (self.user and self.user.role == UserTypes.admin):
            return
        new_status = (
            DebateStatus.closed
            if current == DebateStatus.open
            else DebateStatus.open
        )
        with rx.session() as session:
            set_debate_status(session, debate_id, new_status)
        self._refresh()

    def delete_debate(self, debate_id: int):
        if not (self.user and self.user.role == UserTypes.admin):
            return
        with rx.session() as session:
            delete_debate(session, debate_id)  # admin: delete any debate
        self._refresh()


def debates_admin_page():
    return container(
        navbar(),
        rx.cond(
            DebatesAdminState.is_admin,
            rx.vstack(
                rx.heading("All Debates", size="6"),
                rx.text(
                    "Every debate on the site. Open/close or delete any of them "
                    "— including on behalf of other users.",
                    size="2",
                ),
                rx.cond(
                    DebatesAdminState.rows.length() == 0,
                    rx.callout("No debates have been created yet.", size="1"),
                    rx.fragment(),
                ),
                rx.foreach(
                    DebatesAdminState.rows,
                    lambda r: debate_row(DebatesAdminState, r),
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


@rx.page(route="/debates", on_load=DebatesAdminState.on_load, **page_params)
def debates_admin():
    """Admin-only: moderate all debates."""
    return debates_admin_page()
