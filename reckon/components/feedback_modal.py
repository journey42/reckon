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
    
    def resize_textarea(self):
        """Resize the textarea."""
        return [rx.call_script('resizeTextarea("autoresizing");')]

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
        rx.script(src="/resize_text_area.js"),
        rx.modal(
            rx.modal_overlay(
                rx.modal_content(
                    rx.modal_header(
                        rx.grid(
                            rx.heading("Feedback", size="md"),
                            rx.spacer(),
                            rx.modal_close_button(
                                close_button(
                                    height="15%",
                                    width="15%",
                                    on_click=FeedbackModalState.visible
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
                                        # on_mount=FeedbackModalState.resize_textarea,
                                    ),
                                    submit_button(
                                        type_="submit",
                                        height="5%",
                                        width="5%",
                                        padding_top=4,
                                        align_self="flex-end",
                                        on_click=FeedbackModalState.submit
                                    ),
                                    max_width="850px",
                                ),
                                rx.spacer(max_width="225px"),
                                columns=[3],
                                id="tacontainer",
                                max_height="60vh",
                            )
                        )
                    )
                )
            ),
            is_open=FeedbackModalState.show,
            size="full",
            *args,
            **kwargs
        ),
    )