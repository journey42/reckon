"""comment modal component."""
import reflex as rx
from sqlmodel import select
from datetime import datetime
from reckon.styles import input_style, read_only_text_style
from reckon.components.buttons import support_comment_button, detract_from_comment_button, poo_comment_button, close_button
from reckon.state.base import AppState, Reckoning, ReckoningTypes

class CommentModalState(AppState):
    """Comment state."""
    show: bool = False
    subject: str = ""
    content: str = ""
    type: int = ReckoningTypes.support
    pid: int = 0
    cid: int = 0
    is_editing: bool = False

    def new_comment(self, subject, type, pid):
        print("new comment")
        self.is_editing = False
        self.subject = subject
        self.type = type
        self.pid = pid

    def edit_comment(self, pid, type, cid, content):
        """Set the comment."""
        self.is_editing = True
        self.pid = pid
        with rx.session() as session:
            session.expire_on_commit = False
            parent = session.exec(select(Reckoning).where(Reckoning.id == self.pid)).first()
            self.subject = parent.content
        self.type = type
        self.content = content
        self.cid = cid

    def visible(self):
        """Change the visibility of the comment modal."""
        self.show = not (self.show)

    def submit(self):
        """Submit feedback."""
        print("submit")
        with rx.session() as session:
            if self.is_editing:
                comment = session.exec(select(Reckoning).where(Reckoning.id == self.cid)).first()
                comment.content = self.content
                comment.updated_at = datetime.utcnow()
                session.commit()
            else:
                comment = Reckoning(content=self.content, parent_reckoning_id=self.pid, type=self.type, created_at=datetime.utcnow(), updated_at=datetime.utcnow(), user_id=self.user.id)
                session.add(comment)
                session.commit()
                print("committing")

        self.show = not (self.show)


def comment_modal(*args, **kwargs):
    """Feedback component."""
    return rx.box(
        rx.modal(
            rx.modal_overlay(
                rx.modal_content(
                    rx.modal_header(
                        rx.grid(
                            rx.heading("Comment", size="md"),
                            rx.spacer(),
                            rx.modal_close_button(
                                close_button(
                                    height="15%",
                                    width="15%",
                                    on_click=CommentModalState.visible
                                ),
                            ),
                            grid_template_columns="3fr 5fr 0.25fr",
                        ),
                    ),
                    rx.modal_body(
                        rx.form(
                            rx.vstack(
                                rx.text_area(
                                    value=CommentModalState.subject,
                                    height="30vh",
                                    **read_only_text_style,
                                ),
                                rx.text_area(
                                    default_value=CommentModalState.content,
                                    placeholder="Comment",
                                    height="30vh",
                                    width="100%",
                                    **input_style,
                                    on_blur=CommentModalState.set_content,
                                ),
                                rx.match(
                                    CommentModalState.type,
                                    (ReckoningTypes.support, support_comment_button(width="15%", height="15%", align_self="flex-end", on_click=CommentModalState.submit)),
                                    (ReckoningTypes.point_of_order, poo_comment_button(width="15%", height="15%", align_self="flex-end", on_click=CommentModalState.submit)),
                                    (ReckoningTypes.detract, detract_from_comment_button(width="15%", height="15%", align_self="flex-end", on_click=CommentModalState.submit)),
                                ),
                                id="tacontainer",
                                width="90%",
                            ),
                            display="flex",
                            justify_content="center",
                            align_items="center",
                        ),
                    ),
                )
            ),
            is_open=CommentModalState.show,
            size="full",
            *args,
            **kwargs
        ),
    )