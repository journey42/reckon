"""reckoning feedback modal component."""
import reflex as rx
from datetime import datetime
from typing import List

from reckon.styles import button_style, input_style
from reckon.state.base import AppState, Feedback

options: List[str] = ["Community Guidelines Violation", "Other"]

class ReckoningFeedbackModalState(AppState):
    """Feedback state."""
    show: bool = False
    content: str = ""
    type: str = "No Selection."

    def visible(self):
        """Change the visibility of the feedback modal."""
        self.show = not (self.show)

    def submit(self):
        """Submit feedback."""
        with rx.session() as session:
            feedback = Feedback(content=self.content, type=self.type, created_at=datetime.utcnow(), updated_at=datetime.utcnow(), user_id=self.user.id)
            session.add(feedback)
            #session.expire_on_commit = False
            session.commit()
        self.show = not (self.show)


def reckoning_feedback_modal():
    """reckoning feedback modal component."""
    return rx.box(
        rx.modal(
            rx.modal_overlay(
                rx.modal_content(
                    rx.modal_header("Feedback"),
                    rx.modal_body(
                        rx.form(
                            rx.vstack(
                                rx.select(
                                    options,
                                    placeholder="Type of Feedback",
                                    on_change=ReckoningFeedbackModalState.set_type,
                                    color_schemes="twitter",
                                ),
                                rx.text_area(
                                    placeholder="Feedback",
                                    height="150%",
                                    width="100%",
                                    **input_style,
                                    on_blur=ReckoningFeedbackModalState.set_content,
                                ),
                            )
                        )
                    ),
                    rx.modal_footer(
                        rx.button(
                            "Submit",
                            on_click=ReckoningFeedbackModalState.submit,
                            **button_style,
                            m=2
                        ),
                        rx.button(
                            "Cancel",
                            on_click=ReckoningFeedbackModalState.visible,
                            **button_style,
                            m=2
                        )
                    ),
                )
            ),
            is_open=ReckoningFeedbackModalState.show,
        ),
    )