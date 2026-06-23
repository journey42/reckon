"""Create-debate modal, opened from a concept's card.

The Concept ID is supplied by the card (prefilled, read-only); the admin only
enters a title and intro. On success it redirects to the debate management page
so the new link + QR are immediately available.
"""

import reflex as rx
from sqlmodel import select

from rhiz.state.base import AppState, Reckoning
from rhiz.utils.debates import create_debate, get_debate_for_concept
from rhiz.utils.permissions import can_manage_debates


class DebateDialogState(AppState):
    """State for the create-debate dialog."""

    show: bool = False
    concept_id: int = 0
    title: str = ""
    intro: str = ""
    error: str = ""

    @rx.event
    def open_for(self, cid: int):
        """Open the dialog prefilled for a specific concept."""
        self.concept_id = cid
        self.title = ""
        self.intro = ""
        self.error = ""
        self.show = True

    @rx.event
    def close(self):
        self.show = False

    @rx.event
    def set_title(self, value: str) -> None:
        self.title = value or ""

    @rx.event
    def set_intro(self, value: str) -> None:
        self.intro = value or ""

    @rx.event
    def submit(self):
        """Validate and create the debate, then go to the management page."""
        self.error = ""
        if not can_manage_debates(self.user):
            self.error = "You do not have permission to create debates."
            return
        if not self.title.strip():
            self.error = "Title is required."
            return
        with rx.session() as session:
            concept = session.exec(
                select(Reckoning).where(Reckoning.id == self.concept_id)
            ).first()
            if concept is None:
                self.error = "Concept not found."
                return
            if get_debate_for_concept(session, self.concept_id) is not None:
                self.error = "This concept already has a debate."
                return
            try:
                create_debate(
                    session,
                    self.concept_id,
                    self.title.strip(),
                    self.intro,
                    self.user.id,
                )
            except ValueError as ex:
                self.error = str(ex)
                return
        self.show = False
        return rx.redirect("/debates")


def debate_dialog(*args, **kwargs):
    """The create-debate modal component."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Create Debate"),
                rx.text(
                    "Concept #",
                    DebateDialogState.concept_id,
                    size="1",
                    color="gray",
                ),
                rx.input(
                    placeholder="Title (shown at the top of the debate page)",
                    value=DebateDialogState.title,
                    on_change=DebateDialogState.set_title,
                ),
                rx.text_area(
                    placeholder="Intro / instructions for visitors",
                    value=DebateDialogState.intro,
                    on_change=DebateDialogState.set_intro,
                ),
                rx.cond(
                    DebateDialogState.error != "",
                    rx.callout(
                        DebateDialogState.error, color_scheme="red", size="1"
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            on_click=DebateDialogState.close,
                        ),
                    ),
                    rx.button("Create debate", on_click=DebateDialogState.submit),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                align="stretch",
                width="100%",
            ),
            max_width="480px",
        ),
        open=DebateDialogState.show,
        *args,
        **kwargs,
    )
