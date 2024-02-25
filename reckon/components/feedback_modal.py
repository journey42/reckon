"""general feedback modal component."""
import reflex as rx
from datetime import datetime
from typing import List, Optional
from reckon.styles import input_style
from reckon.state.base import AppState, Feedback, Reckoning
from reckon.components.buttons import submit_button, close_button

general_feedback_options: List[str] = ["Technical Problem", "Rhetorical Issue", "Other"]
reckoning_feedback_options: List[str] = ["Community Guidelines Violation", "Other"]

class FeedbackModalState(AppState):
    """Feedback state."""
    show: bool = False
    content: str
    type: str
    reckoning_id: Optional[int] = None

    def visible(self):
        """Change the visibility of the feedback modal."""
        self.show = not (self.show)

    def close(self):
        pass

    def set_reckoning(self, rid):
        """Set the content of the feedback."""
        self.reckoning_id = rid

    @rx.var
    def is_error(self) -> bool:
        return self.type == ""
    
    def submit(self):
        """submit feedback."""
        if(self.is_error):
            return
        with rx.session() as session:
            if self.reckoning_id:
                feedback = Feedback(content=self.content, type=self.type, created_at=datetime.utcnow(), updated_at=datetime.utcnow(), user_id=self.user.id, subject_reckoning_id=self.reckoning_id)
            else:
                feedback = Feedback(content=self.content, type=self.type, created_at=datetime.utcnow(), updated_at=datetime.utcnow(), user_id=self.user.id)
            session.add(feedback)
            #session.expire_on_commit = False
            session.commit()
        self.show = not (self.show)


def feedback_modal(options: List[str], *args, **kwargs):
    """feedback modal component."""
    return rx.box(
        rx.modal(
            rx.modal_overlay(
                rx.modal_content(
                    rx.modal_header(
                        rx.grid(
                            rx.heading("Feedback", size="md"),
                            rx.spacer(),
                            rx.modal_close_button(
                                close_button(
                                    on_click=FeedbackModalState.visible
                                ),
                            ),
                            grid_template_columns="3fr 5fr 1fr",
                        ),
                    ),
                    rx.modal_body(
                        rx.form(
                            rx.vstack(
                                rx.form_control(
                                    rx.select(
                                        options,
                                        is_required=True,
                                        placeholder="Type of Feedback",
                                        on_change=FeedbackModalState.set_type,
                                        color_schemes="twitter",
                                    ),
                                    rx.cond(
                                        FeedbackModalState.is_error,
                                        rx.form_error_message(
                                            "Feedback type is required."
                                        ),
                                    ),
                                    is_invalid=FeedbackModalState.is_error,
                                    is_required=True,
                                ),
                                rx.text_area(
                                    id="autoresizing",
                                    placeholder="Feedback",
                                    height="60vh",
                                    width="100%",
                                    **input_style,
                                    on_blur=FeedbackModalState.set_content,
                                ),
                                submit_button(
                                    max_width="48px",
                                    max_height="48px",
                                    padding_top=4,
                                    align_self="flex-end",
                                    on_click=FeedbackModalState.submit
                                ),
                                id="tacontainer",
                                width="90%",
                            ),
                            display="flex",
                            justify_content="center",
                            align_items="center",
                        ),
                    )
                )
            ),
            is_open=FeedbackModalState.show,
            size="full",
            *args,
            **kwargs
        ),
    )