"""comment modal component."""

import reflex as rx
from sqlmodel import select
from datetime import datetime, timezone
from rhiz.styles import dialog_button_style, read_only_text_style
from rhiz.components.buttons import (
    support_comment_button,
    detract_from_comment_button,
    poo_comment_button,
    close_button,
)
from rhiz.state.base import AppState, Reckoning, ReckoningTypes
from rhiz.components.tiptap_editor import TiptapEditor
from rhiz.components.safe_markdown import SafeMarkdown


class CommentDialogState(AppState):
    """Comment state."""

    show: bool = False
    subject: str = ""
    content: str = ""
    type: int = ReckoningTypes.support
    pid: int = 0
    cid: int = 0
    is_editing: bool = False

    @rx.event
    def new_comment(self, subject, type, pid):
        self.is_editing = False
        self.subject = subject
        self.type = type
        self.pid = pid
        # reset to avoid errors
        self.cid = 0
        self.content = ""

    @rx.event
    def edit_comment(self, pid, type, cid, content):
        """Set the comment."""
        self.is_editing = True
        self.pid = pid
        with rx.session() as session:
            session.expire_on_commit = False
            parent = session.exec(
                select(Reckoning).where(Reckoning.id == self.pid)
            ).first()
            self.subject = parent.content
        self.type = type
        self.content = content
        self.cid = cid

    @rx.event
    def visible(self):
        """Change the visibility of the comment modal."""
        self.show = not (self.show)

    @rx.event
    def set_content(self, value: str) -> None:
        self.content = value or ""

    @rx.event
    def submit(self):
        """Submit feedback."""
        with rx.session() as session:
            if self.content == "":
                return
            # comment_content = "This reckoning did not include a comment. Feel free to add one."

            # if self.content != "":
            #     comment_content = self.content

            if self.is_editing:
                comment = session.exec(
                    select(Reckoning).where(Reckoning.id == self.cid)
                ).first()
                comment.content = self.content
                comment.updated_at = datetime.now(timezone.utc)
                session.commit()
                self.show = not (self.show)
            else:
                comment = Reckoning(
                    content=self.content,
                    parent_reckoning_id=self.pid,
                    type=self.type,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    user_id=self.user.id,
                )
                session.add(comment)
                session.commit()
                self.show = not (self.show)
                # yield rx.redirect(f"/comments/{comment.id}")


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
                            **dialog_button_style, on_click=CommentDialogState.visible
                        ),
                    ),
                    grid_template_columns="3fr 5fr 1fr",
                ),
            ),
            rx.form(
                rx.vstack(
                    rx.box(
                        SafeMarkdown.create(
                            content=CommentDialogState.subject,
                            class_name="prose",
                            max_width="100%",
                            **read_only_text_style,
                        ),
                        width="100%",
                        max_height="20vh",
                        overflow_y="auto",
                        padding="12px",
                        border="1px solid #e2e8f0",
                        border_radius="8px",
                        background="#f8fafc",
                    ),
                    TiptapEditor.create(
                        value=CommentDialogState.content,
                        placeholder="Comment",
                        height="25vh",
                        toolbar_enabled=True,
                        on_change=CommentDialogState.set_content,
                    ),
                    rx.match(
                        CommentDialogState.type,
                        (
                            ReckoningTypes.support,
                            support_comment_button(
                                **dialog_button_style,
                                align_self="flex-end",
                                on_click=CommentDialogState.submit
                            ),
                        ),
                        (
                            ReckoningTypes.point_of_order,
                            poo_comment_button(
                                **dialog_button_style,
                                align_self="flex-end",
                                on_click=CommentDialogState.submit
                            ),
                        ),
                        (
                            ReckoningTypes.detract,
                            detract_from_comment_button(
                                **dialog_button_style,
                                align_self="flex-end",
                                on_click=CommentDialogState.submit
                            ),
                        ),
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
