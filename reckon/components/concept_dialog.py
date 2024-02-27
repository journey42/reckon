"""concept modal component."""
import reflex as rx
from datetime import datetime
from sqlmodel import select
from typing import Optional
from reckon.styles import input_style
from reckon.state.base import AppState, Reckoning
from reckon.components.buttons import submit_button, close_button

class ConceptDialogState(AppState):
    """Concept modal state."""
    show: bool = False
    content: str = ""
    concept: Optional["Reckoning"]

    def set_concept(self, cid):
        """Set the concept."""
        with rx.session() as session:
                self.concept = session.exec(select(Reckoning).where(Reckoning.id == cid)).first()
                self.content = self.concept.content
        
    def visible(self):
        """Change the visibility of the modal."""
        self.show = not (self.show)

    def resize_textarea(self):
        """Resize the textarea."""
        return [rx.call_script('resizeTextarea("autoresizing");')]

    def submit(self):
        """Submit."""
        with rx.session() as session:
            session.expire_on_commit = False
            self.concept = session.merge(self.concept)
            self.concept.content = self.content
            self.concept.updated_at = datetime.utcnow()
            session.commit()
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
                                        on_click=ConceptDialogState.visible
                                    ),
                                ),
                                grid_template_columns="3fr 5fr 1fr",
                            ),
                        ),
                        rx.text_area(
                            id="autoresizing",
                            value=ConceptDialogState.content,
                            placeholder="Concept",
                            height="60vh",
                            width="100%",
                            **input_style,
                            on_change=ConceptDialogState.set_content,
                        ),
                        submit_button(
                            max_width="48px",
                            max_height="48px",
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
            **kwargs
        )