"""comment modal component."""
import reflex as rx
from datetime import datetime

from reckon.styles import input_style
from reckon.components.buttons import support_comment_button, detract_from_comment_button, poo_comment_button
from reckon.state.base import AppState, Reckoning, ReckoningTypes

class CommentModalState(AppState):
    """Comment state."""
    show: bool = False
    subject: str = ""
    content: str = ""
    type: int = ReckoningTypes.support
    pid: int = 0

    def init(self, subject, type, pid):
        self.subject = subject
        self.type = type
        self.pid = pid
        self.show = not (self.show)

    def visible(self):
        """Change the visibility of the comment modal."""
        self.show = not (self.show)

    def submit(self):
        """Submit feedback."""
        with rx.session() as session:
            if self.content != "":
                comment = Reckoning(content=self.content, parent_reckoning_id=self.pid, type=self.type, created_at=datetime.utcnow(), updated_at=None, user_id=self.user.id)
                session.add(comment)
            
            #session.expire_on_commit = False
            session.commit()
        self.show = not (self.show)


def comment_modal():
    """Feedback component."""
    return rx.box(
        rx.modal(
            rx.modal_overlay(
                rx.modal_content(
                    rx.modal_header(
                        rx.grid(
                            rx.heading("Comment"),
                            rx.spacer(),
                            rx.text("x", on_click=CommentModalState.visible, style={"cursor": "pointer"}),
                            grid_template_columns="3fr 5fr 0.25fr",
                        ),
                    ),
                    rx.modal_body(
                        rx.form(
                            rx.vstack(
                                rx.text_area(
                                    is_read_only=True,
                                    value=CommentModalState.subject,
                                    height="150%",
                                    width="100%",
                                    **input_style,
                                ),
                                rx.text_area(
                                    placeholder="Comment",
                                    height="150%",
                                    width="100%",
                                    **input_style,
                                    on_blur=CommentModalState.set_content,
                                ),
                            ),
                        ),
                    ),
                    rx.modal_footer(
                        rx.match(
                            CommentModalState.type,
                            (ReckoningTypes.support, support_comment_button(width="15%", height="15%", on_click=CommentModalState.submit)),
                            (ReckoningTypes.point_of_order, poo_comment_button(width="15%", height="15%", on_click=CommentModalState.submit)),
                            (ReckoningTypes.detract, detract_from_comment_button(width="15%", height="15%", on_click=CommentModalState.submit)),
                        ),
                    ),
                )
            ),
            is_open=CommentModalState.show,
        ),
    )