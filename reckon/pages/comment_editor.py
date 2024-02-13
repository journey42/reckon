"""comment editor modal component."""
import reflex as rx
from datetime import datetime
from sqlmodel import select
from reckon.styles import page_params, control_panel_text_style
from reckon.components.buttons import support_comment_button, detract_from_comment_button, poo_comment_button
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.components.navbar import navbar


class CommentEditorPageState(AppState):
    """Comment editor state."""
    comment: Reckoning = None
    parent_reckoning: Reckoning = None
    comment_type: int = ReckoningTypes.support
    content: str = ""
    subject: str = ""
    is_editing: bool = False

    def get_parent(self, prid):
        """Get parent reckoning from the database."""
        with rx.session() as session:
                self.parent_reckoning = session.exec(select(Reckoning).where(Reckoning.id == prid)).first()

    def get_comment(self, cid):
        """Get reckoning with id of cid from the database."""
        with rx.session() as session:
                self.comment = session.exec(select(Reckoning).where(Reckoning.id == cid)).first()

    def on_load_new_comment_on_parent(self):
        self.check_login()
        self.is_editing = False
        self.get_parent(self.parent_reckoning_id)
        self.get_comment(self.comment_id)
        self.subject = self.parent_reckoning.content
        self.content = ""
        self.comment_type = self.type

    def on_load_new_comment(self):
        self.check_login()
        self.is_editing = False
        self.get_parent(self.parent_reckoning_id)
        self.get_comment(self.comment_id)
        self.subject = self.comment.content
        self.content = ""
        self.comment_type = self.type

    def on_load_existing_comment(self):
        self.check_login()
        self.is_editing = True
        self.get_parent(self.parent_reckoning_id)
        self.get_comment(self.comment_id)
        self.subject = self.parent_reckoning.content
        self.content = self.comment.content
        self.comment_type = self.comment.type

    @rx.var
    def comment_id(self):
        return self.router.page.params.get('cid', None)
   
    @rx.var
    def parent_reckoning_id(self):
        return self.router.page.params.get('prid', None)
    
    @rx.var
    def type(self):
        return int(self.router.page.params.get('type', "5"))

    def submit(self):
        """Submit comment."""
        with rx.session() as session:
            session.expire_on_commit = False
            if self.is_editing:
                if self.comment is not None:
                    self.comment.content = self.content
                    self.comment.updated_at = datetime.utcnow()
                    session.add(self.comment)
            else:
                comment = Reckoning(content=self.content, parent_reckoning_id=self.comment.id, type=self.comment_type, created_at=datetime.utcnow(), updated_at=datetime.utcnow(), user_id=self.user.id)
                session.add(comment)
                print("comment added", comment)

            session.commit()


        self.content = ""
        self.is_editing = False
        self.subject = ""
        yield rx.redirect(f'/comments/{self.parent_reckoning.id}')

def edit_control():
    return rx.box(
            rx.grid(
                rx.grid(
                    rx.heading("Comment", size="sm"),
                    rx.spacer(),
                    rx.text("x", on_click=rx.redirect(f'/comments/{CommentEditorPageState.parent_reckoning_id}'), style={"cursor": "pointer"}),
                    grid_template_columns="3fr 5fr 0.25fr",
                ),
                rx.grid(
                    rx.text_area(
                        is_read_only=True,
                        value=CommentEditorPageState.subject,
                        width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em",
                    ),
                    rx.text_area(
                        default_value=CommentEditorPageState.content,
                        placeholder="Comment",
                        width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em",
                        on_blur=CommentEditorPageState.set_content,
                    ),
                    gap="2",
                ),
                rx.grid(
                    rx.spacer(),
                    rx.spacer(),
                    rx.match(
                        CommentEditorPageState.comment_type,
                        (ReckoningTypes.support, support_comment_button(width="15%", height="15%", on_click=CommentEditorPageState.submit)),
                        (ReckoningTypes.point_of_order, poo_comment_button(width="15%", height="15%", on_click=CommentEditorPageState.submit)),
                        (ReckoningTypes.detract, detract_from_comment_button(width="15%", height="15%", on_click=CommentEditorPageState.submit)),
                    ),
                    grid_template_columns="3fr 6fr 1fr",
                    **control_panel_text_style,
                ),
                gap=4,
                padding=2,
            ),
            width="100%",
            border="1px solid #ededed",
    )

@rx.page(route="/comment_editor/[prid]/[cid]", on_load=CommentEditorPageState.on_load_existing_comment, **page_params)
def comment_editor():
    """Comment Editor."""
    return rx.container(
        navbar(),
        edit_control(),
        max_width="1300px",
    )

@rx.page(route="/new_comment_editor/[prid]/[cid]/[type]", on_load=CommentEditorPageState.on_load_new_comment, **page_params)
def new_comment_editor():
    """Comment Editor."""
    return rx.container(
        navbar(),
        edit_control(),
        max_width="1300px",
    )

@rx.page(route="/new_comment_on_parent_editor/[prid]/[cid]/[type]", on_load=CommentEditorPageState.on_load_new_comment_on_parent, **page_params)
def new_comment_on_parent_editor():
    """Comment Editor."""
    return rx.container(
        navbar(),
        edit_control(),
        max_width="1300px",
    )