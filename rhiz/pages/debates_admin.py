"""Admin page: create and manage distributable debates."""

import os
import reflex as rx
from sqlmodel import select

from rhiz.state.base import AppState, Reckoning, Debate, DebateStatus
from rhiz.utils.debates import create_debate, set_debate_status
from rhiz.utils.permissions import can_manage_debates
from rhiz.utils.qr import qr_data_uri
from rhiz.styles import page_params
from rhiz.components import container, navbar


class DebatesAdminState(AppState):
    rows: list[dict] = []
    concept_id_input: str = ""
    title_input: str = ""
    intro_input: str = ""
    error: str = ""

    @rx.var
    def can_manage(self) -> bool:
        return can_manage_debates(self.user)

    def _base_url(self) -> str:
        """Public origin for debate share links. Set PUBLIC_BASE_URL in
        production (e.g. https://reckon.cc); defaults to the local dev
        frontend. Trailing slash is stripped."""
        return os.environ.get("PUBLIC_BASE_URL", "http://localhost:3000").rstrip("/")

    def on_load(self):
        result = self.check_login()
        if result:
            return result
        self._refresh()

    def _refresh(self):
        self.rows = []
        if not can_manage_debates(self.user):
            return
        base = self._base_url()
        with rx.session() as session:
            debates = session.exec(select(Debate).order_by(Debate.created_at.desc())).all()
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

    def set_concept_id_input(self, v: str):
        self.concept_id_input = v or ""

    def set_title_input(self, v: str):
        self.title_input = v or ""

    def set_intro_input(self, v: str):
        self.intro_input = v or ""

    def create(self):
        self.error = ""
        if not can_manage_debates(self.user):
            self.error = "Not authorized."
            return
        try:
            cid = int(self.concept_id_input)
        except ValueError:
            self.error = "Concept ID must be a number."
            return
        if not self.title_input.strip():
            self.error = "Title is required."
            return
        with rx.session() as session:
            concept = session.exec(select(Reckoning).where(Reckoning.id == cid)).first()
            if concept is None:
                self.error = f"No concept with id {cid}."
                return
            try:
                create_debate(session, cid, self.title_input.strip(), self.intro_input, self.user.id)
            except ValueError as ex:
                self.error = str(ex)
                return
        self.concept_id_input = ""
        self.title_input = ""
        self.intro_input = ""
        self._refresh()

    def toggle_status(self, debate_id: int, current: str):
        new_status = DebateStatus.closed if current == DebateStatus.open else DebateStatus.open
        with rx.session() as session:
            set_debate_status(session, debate_id, new_status)
        self._refresh()


def _row(r: dict):
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.heading(r["title"], size="3"),
                rx.link(r["url"], href=r["url"], size="1"),
                rx.text("Status: ", r["status"], size="1"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.image(src=r["qr"], width="96px", height="96px"),
            rx.button(
                rx.cond(r["status"] == DebateStatus.open, "Close", "Reopen"),
                on_click=DebatesAdminState.toggle_status(r["id"], r["status"]),
                variant="soft",
                size="1",
            ),
            align="center",
            width="100%",
        ),
        width="100%",
    )


def debates_admin_page():
    return container(
        navbar(),
        rx.cond(
            DebatesAdminState.can_manage,
            rx.vstack(
                rx.heading("Debates", size="6"),
                rx.text("Turn a concept into a distributable debate page.", size="2"),
                rx.card(
                    rx.vstack(
                        rx.input(
                            placeholder="Concept ID",
                            value=DebatesAdminState.concept_id_input,
                            on_change=DebatesAdminState.set_concept_id_input,
                        ),
                        rx.input(
                            placeholder="Title",
                            value=DebatesAdminState.title_input,
                            on_change=DebatesAdminState.set_title_input,
                        ),
                        rx.text_area(
                            placeholder="Intro / instructions",
                            value=DebatesAdminState.intro_input,
                            on_change=DebatesAdminState.set_intro_input,
                        ),
                        rx.button("Create debate", on_click=DebatesAdminState.create),
                        rx.cond(
                            DebatesAdminState.error != "",
                            rx.callout(DebatesAdminState.error, color_scheme="red", size="1"),
                            rx.fragment(),
                        ),
                        spacing="2",
                        align="stretch",
                    ),
                ),
                rx.foreach(DebatesAdminState.rows, _row),
                spacing="4",
                align="stretch",
                width="100%",
                padding="24px",
            ),
            rx.center(
                rx.text("You do not have access to debate management."),
                min_height="50vh",
            ),
        ),
    )


@rx.page(route="/debates", on_load=DebatesAdminState.on_load, **page_params)
def debates_admin():
    """Admin debate management page."""
    return debates_admin_page()
