"""concept modal component."""

import reflex as rx
from datetime import datetime, timezone
from sqlmodel import select
from typing import Optional
from rhiz.styles import dialog_button_style
from rhiz.state.base import AppState, Reckoning
from rhiz.components.buttons import submit_button, close_button
from rhiz.utils.db import insert_text_with_embedding
from rhiz.utils.parsing import remove_html_tags
from rhiz.components.editor import editor


class ConceptDialogState(AppState):
    """Concept modal state."""

    show: bool = False
    content: str = ""
    concept: Optional["Reckoning"] = None

    @rx.event
    def set_concept(self, cid):
        """Set the concept."""
        with rx.session() as session:
            concept = session.exec(select(Reckoning).where(Reckoning.id == cid)).first()
            self.concept = concept
            self.content = concept.content if concept else ""

    @rx.event
    def visible(self):
        """Change the visibility of the modal."""
        self.show = not (self.show)

    @rx.event
    def set_content(self, value: str) -> None:
        self.content = value or ""

    def resize_textarea(self):
        """Resize the textarea."""
        return [rx.call_script('resizeTextarea("autoresizing");')]

    @rx.event
    def submit(self):
        """Submit."""
        with rx.session() as session:
            session.expire_on_commit = False
            if self.concept is None:
                return
            concept = session.merge(self.concept)
            concept.content = self.content
            concept.updated_at = datetime.now(timezone.utc)
            session.commit()

        cleaned = remove_html_tags(self.concept.content) if self.concept else ""
        if self.concept:
            insert_text_with_embedding(cleaned, self.concept.id)
        self.visible()
        return rx.redirect("/your_drafts")


def concept_dialog(*args, **kwargs):
    """concept modal component."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title(
                    rx.grid(
                        rx.heading("Edit Concept", size="5"),
                        rx.spacer(),
                        rx.dialog.close(
                            close_button(
                                **dialog_button_style,
                                align_self="flex-end",
                                on_click=ConceptDialogState.visible,
                            ),
                        ),
                        grid_template_columns="4fr 9fr 1fr",
                    ),
                ),
                editor(
                    name="concept_content",
                    default_value=ConceptDialogState.content,
                    placeholder="Concept",
                    height="40vh",
                    width="100%",
                    on_blur=ConceptDialogState.set_content,
                ),
                submit_button(
                    **dialog_button_style,
                    on_click=ConceptDialogState.submit,
                    align_self="flex-end",
                ),
                id="tacontainer",
                width="90%",
            ),
            display="flex",
            justify_content="center",
            align_items="center",
        ),
        open=ConceptDialogState.show,
        size="4",
        *args,
        **kwargs,
    )
