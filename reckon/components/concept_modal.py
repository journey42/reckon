"""concept modal component."""
import reflex as rx
from datetime import datetime
from sqlmodel import select
from typing import Optional
from reckon.styles import input_style
from reckon.state.base import AppState, Reckoning
from reckon.components.buttons import submit_button, close_button

class ConceptModalState(AppState):
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

def concept_modal(*args, **kwargs):
    """concept modal component."""
    return rx.box(
        rx.script(src="/resize_text_area.js"),
        rx.modal(
            rx.modal_overlay(
                rx.modal_content(
                    rx.modal_header(
                        rx.grid(
                            rx.heading("Edit Concept", size="md"),
                            rx.spacer(),
                            rx.modal_close_button(
                                close_button(
                                    height="15%",
                                    width="15%",
                                    on_click=ConceptModalState.visible
                                ),
                            ),
                            grid_template_columns="3fr 5fr 1fr",
                        ),
                    ),
                    rx.modal_body(
                        rx.form(
                            rx.responsive_grid(
                                rx.spacer(max_width="225px"),
                                rx.vstack(
                                    rx.text_area(
                                         id="autoresizing",
                                        default_value=ConceptModalState.content,
                                        placeholder="Concept",
                                        max_height="80vh",
                                        width="100%",
                                        **input_style,
                                        on_blur=ConceptModalState.set_content,
                                        on_mount=ConceptModalState.resize_textarea,
                                    ),
                                    submit_button(
                                        height="5%",
                                        width="5%",
                                        on_click=ConceptModalState.submit,
                                        align_self="flex-end",
                                    ),
                                    max_width="850px",
                                ),
                                rx.spacer(max_width="225px"),
                                columns=[3],
                                id="tacontainer",
                                max_height="80vh",
                            )
                        )
                    )
                )
            ),
            is_open=ConceptModalState.show,
            size="full",
            *args,
            **kwargs
        ),
    )