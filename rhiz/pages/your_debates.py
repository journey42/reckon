"""Per-user page: the current user's own debates (/your_debates).

Visible to anyone entitled to create debates (DEBATE_CREATE_MIN_ROLE). Lists
only the debates this user created, with share link + QR, and lets them
open/close or delete their own. Site-wide moderation lives on the admin-only
/debates page.
"""

import reflex as rx
from sqlmodel import select

from rhiz.state.base import AppState, Debate, DebateStatus
from rhiz.utils.debates import set_debate_status, delete_debate
from rhiz.utils.permissions import can_manage_debates
from rhiz.utils.qr import qr_data_uri
from rhiz.styles import page_params
from rhiz.components import container, navbar
from rhiz.pages.debate_common import public_base_url, debate_row


class YourDebatesState(AppState):
    rows: list[dict] = []

    @rx.var
    def can_manage(self) -> bool:
        return can_manage_debates(self.user)

    def on_load(self):
        result = self.check_login()
        if result:
            return result
        self._refresh()

    def _refresh(self):
        self.rows = []
        if not can_manage_debates(self.user):
            return
        base = public_base_url()
        with rx.session() as session:
            debates = session.exec(
                select(Debate)
                .where(Debate.created_by == self.user.id)
                .order_by(Debate.created_at.desc())
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
        if not can_manage_debates(self.user):
            return
        new_status = (
            DebateStatus.closed
            if current == DebateStatus.open
            else DebateStatus.open
        )
        with rx.session() as session:
            # owner_id guard: only act on the user's own debate
            debate = session.exec(
                select(Debate).where(Debate.id == debate_id)
            ).first()
            if debate is not None and debate.created_by == self.user.id:
                set_debate_status(session, debate_id, new_status)
        self._refresh()

    def delete_debate(self, debate_id: int):
        if not can_manage_debates(self.user):
            return
        with rx.session() as session:
            delete_debate(session, debate_id, owner_id=self.user.id)
        self._refresh()


def your_debates_page():
    return container(
        navbar(),
        rx.cond(
            YourDebatesState.can_manage,
            rx.vstack(
                rx.heading("Your Debates", size="6"),
                rx.text(
                    "Debates you've created. Share the link or QR code, and "
                    "open/close or delete them here.",
                    size="2",
                ),
                rx.cond(
                    YourDebatesState.rows.length() == 0,
                    rx.callout(
                        "You haven't created any debates yet. Open the ⋯ "
                        "menu on one of your concepts and choose Create Debate.",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                rx.foreach(
                    YourDebatesState.rows,
                    lambda r: debate_row(YourDebatesState, r),
                ),
                spacing="4",
                align="stretch",
                width="100%",
                padding="24px",
            ),
            rx.center(
                rx.text("You do not have access to debates."),
                min_height="50vh",
            ),
        ),
    )


@rx.page(route="/your_debates", on_load=YourDebatesState.on_load, **page_params)
def your_debates():
    """The current user's own debates."""
    return your_debates_page()
