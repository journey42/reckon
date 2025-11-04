"""general feedback modal component."""

import reflex as rx
from datetime import datetime, timezone
from typing import List, Optional
from rhiz.styles import input_style, dialog_button_style
from rhiz.state.base import AppState, Feedback, Reckoning
from rhiz.components.buttons import submit_button, close_button

general_feedback_options: List[str] = ["Technical Problem", "Rhetorical Issue", "Other"]
reckoning_feedback_options: List[str] = ["Community Guidelines Violation", "Other"]


class FeedbackDialogState(AppState):
    """Feedback state."""

    show: bool = False
    content: str = ""
    type: str = ""
    reckoning_id: Optional[int] = None

    @rx.event
    def visible(self):
        """Change the visibility of the feedback modal."""
        self.show = not (self.show)

    @rx.event
    def close(self):
        pass

    @rx.event
    def set_reckoning(self, rid):
        """Set the content of the feedback."""
        self.reckoning_id = rid

    @rx.event
    def set_type(self, value: str) -> None:
        self.type = (value or "").strip()

    @rx.event
    def set_content(self, value: str) -> None:
        self.content = value or ""

    @rx.var
    def is_error(self) -> bool:
        return self.type == ""

    @rx.event
    def submit(self, form_data: dict):
        """submit feedback."""
        if self.is_error:
            return
        with rx.session() as session:
            if self.reckoning_id:
                feedback = Feedback(
                    content=self.content,
                    type=self.type,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    user_id=self.user.id,
                    subject_reckoning_id=self.reckoning_id,
                )
            else:
                feedback = Feedback(
                    content=self.content,
                    type=self.type,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    user_id=self.user.id,
                )
            session.add(feedback)
            # session.expire_on_commit = False
            session.commit()
        self.show = not (self.show)


def feedback_dialog(options: List[str], *args, **kwargs):
    """feedback modal component."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.grid(
                    rx.heading("Feedback", size="5"),
                    rx.spacer(),
                    rx.dialog.close(
                        close_button(
                            **dialog_button_style, on_click=FeedbackDialogState.visible
                        ),
                    ),
                    grid_template_columns="3fr 5fr 1fr",
                ),
            ),
            rx.form(
                rx.vstack(
                    rx.form.field(
                        rx.select(
                            options,
                            is_required=True,
                            placeholder="Type of Feedback",
                            on_change=FeedbackDialogState.set_type,
                            color_schemes="twitter",
                        ),
                        rx.cond(
                            FeedbackDialogState.is_error,
                            rx.text(
                                "Feedback type is required.",
                                color="red",
                                font_size="0.9em",
                            ),
                        ),
                        server_invalid=FeedbackDialogState.is_error,
                        is_required=True,
                    ),
                    rx.text_area(
                        id="autoresizing",
                        placeholder="Feedback",
                        height="60vh",
                        **input_style,
                        on_change=FeedbackDialogState.set_content,
                    ),
                    submit_button(
                        **dialog_button_style,
                        padding_top=4,
                        align_self="flex-end",
                        type="submit",
                    ),
                    id="tacontainer",
                    width="90%",
                ),
                display="flex",
                justify_content="center",
                align_items="center",
                on_submit=FeedbackDialogState.submit,
            ),
            size="4",
        ),
        open=FeedbackDialogState.show,
        *args,
        **kwargs,
    )
