"""comment modal component."""
import reflex as rx
from sqlmodel import select
from datetime import datetime
from reckon.styles import input_style, read_only_text_style
from reckon.components.buttons import support_comment_button, detract_from_comment_button, poo_comment_button, close_button
from reckon.state.base import AppState, Reckoning, ReckoningTypes

class CommentDialogState(AppState):
    """Comment state."""
    show: bool = False
    subject: str = ""
    content: str = ""
    type: int = ReckoningTypes.support
    pid: int = 0
    cid: int = 0
    is_editing: bool = False

    def new_comment(self, subject, type, pid):
        self.is_editing = False
        self.subject = subject
        self.type = type
        self.pid = pid
        #reset to avoid errors
        self.cid = 0
        self.content = ""

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
        with rx.session() as session:
            comment_content = "This reckoning did not include a comment. Feel free to add one."

            if self.content != "":
                comment_content = self.content

            if self.is_editing:
                comment = session.exec(select(Reckoning).where(Reckoning.id == self.cid)).first()
                comment.content = comment_content
                comment.updated_at = datetime.utcnow()
                session.commit()
                self.show = not (self.show)
            else:
                comment = Reckoning(content=comment_content, parent_reckoning_id=self.pid, type=self.type, created_at=datetime.utcnow(), updated_at=datetime.utcnow(), user_id=self.user.id)
                session.add(comment)
                session.commit()
                self.show = not (self.show)
                #yield rx.redirect(f"/comments/{comment.id}")


def comment_dialog(*args, **kwargs):
    """Feedback component."""
    return rx.dialog.root(
                rx.dialog.content(
                    rx.dialog.title(
                        rx.grid(
                            rx.heading("Comment", size="5"),
                            rx.spacer(),
                            rx.dialog.close(
                                close_button(
                                    on_click=CommentDialogState.visible
                                ),
                            ),
                            grid_template_columns="3fr 5fr 1fr",
                        ),
                    ),
                    rx.form(
                        rx.vstack(
                            rx.text_area(
                                value=CommentDialogState.subject,
                                height="30vh",
                                width="100%",
                                style=read_only_text_style,
                            ),
                            rx.text_area(
                                value=CommentDialogState.content,
                                placeholder="Comment",
                                height="30vh",
                                width="100%",
                                **input_style,
                                on_change=CommentDialogState.set_content,
                            ),
                            rx.match(
                                CommentDialogState.type,
                                (ReckoningTypes.support, support_comment_button(max_width="48px", max_height="48px", align_self="flex-end", on_click=CommentDialogState.submit)),
                                (ReckoningTypes.point_of_order, poo_comment_button(max_width="48px", max_height="48px", align_self="flex-end", on_click=CommentDialogState.submit)),
                                (ReckoningTypes.detract, detract_from_comment_button(max_width="48px", max_height="48px", align_self="flex-end", on_click=CommentDialogState.submit)),
                            ),
                            id="tacontainer",
                            width="90%",
                        ),
                        display="flex",
                        justify_content="center",
                        align_items="center",
                    ),
                ),
                open=CommentDialogState.show,
                size="4",
                *args,
                **kwargs
            )