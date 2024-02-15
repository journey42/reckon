"""The comments page."""
import reflex as rx
from reckon.styles import input_style_focus, page_params, control_panel_text_style
from ..components import container
from ..components import navbar
from reckon.components.buttons import view_children_button, delete_button, support_comment_button, detract_from_comment_button, poo_comment_button, feedback_button,  view_parent_button, edit_button, no_edit_button, no_delete_button
from reckon.components.reckoning_feedback_modal import reckoning_feedback_modal, ReckoningFeedbackModalState
from sqlalchemy import and_ as _and
from sqlmodel import select, delete
from reckon.state.base import AppState, Reckoning, ReckoningTypes

class CommentsPageState(AppState):
    """The state for the your history page."""
    def get_comments(self, rid):
        """Get comments for this reckoning from the database."""
        with rx.session() as session:
            if self.search:
                self.comments = session.exec(
                    select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.content.contains(self.search), Reckoning.parent_reckoning_id == rid))
                ).unique().all()
            else:
                self.comments = session.exec(select(Reckoning).order_by(Reckoning.created_at.desc()).where(Reckoning.parent_reckoning_id == rid)
                ).unique().all()

            for r in self.comments:
                r.compute_tallies(self.user.id)

    content: str
    comments: list[Reckoning] = []
    search: str
    parent: Reckoning = None

    def delete_reckoning(self, rid):
        """Delete a reckoning."""
        with rx.session() as session:
            session.exec(delete(Reckoning).where(Reckoning.id == rid))
            session.commit()
        return self.get_comments(self.reckoning_id)
    
    def set_search(self, search):
        """Set the search query."""
        self.search = search
        return self.get_comments(self.reckoning_id)
    
    def get_parent(self, rid):
        """Get parent reckoning."""
        with rx.session() as session:
                self.parent = session.exec(select(Reckoning).where(Reckoning.id == rid)).first()

    def on_load(self):
        print("on load comments page")
        self.check_login()
        self.get_parent(self.reckoning_id)
        self.get_comments(self.reckoning_id)

    @rx.var
    def reckoning_id(self) -> str:
        return self.router.page.params.get('rid', 'no rid')


def render_comment(c: Reckoning):
    """Display for an individual comment in the feed."""
    return rx.grid(
        rx.grid(
            rx.match(
                c.type,
                (ReckoningTypes.support, support_comment_button(height="15%", width="15%")),
                (ReckoningTypes.detract, detract_from_comment_button(height="15%", width="15%")),
                (ReckoningTypes.point_of_order, poo_comment_button(height="15%", width="15%")),
            ),
            rx.text_area(default_value=c.content, is_read_only=True, width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em"),
            grid_template_columns="1fr 12fr",
            py=1,
            px=1,
            gap=1,
            **control_panel_text_style,
        ),
        rx.grid (
                rx.text(c.supports),
                rx.text(c.points_of_order),
                rx.text(c.detracts),
                rx.spacer(),
                support_comment_button(
                    height="15%",
                    width="15%",
                    on_click=rx.redirect(f'/new_comment_editor/{CommentsPageState.reckoning_id}/{c.id}/{ReckoningTypes.support}')
                ),
                poo_comment_button(
                    height="15%",
                    width="15%",
                    on_click=rx.redirect(f'/new_comment_editor/{CommentsPageState.reckoning_id}/{c.id}/{ReckoningTypes.point_of_order}')
                ),
                detract_from_comment_button(
                    height="15%",
                    width="15%",
                    on_click=rx.redirect(f'/new_comment_editor/{CommentsPageState.reckoning_id}/{c.id}/{ReckoningTypes.detract}')
                ),
                feedback_button(
                    height="15%",
                    width="15%",
                    on_click=ReckoningFeedbackModalState.visible,
                ),
                rx.cond(
                    ((CommentsPageState.user.role > 0) | ((c.user_id == CommentsPageState.user.id) & (c.supports == 0) & (c.detracts == 0) & (c.points_of_order == 0))),
                    edit_button(
                        height="15%",
                        width="15%",
                        on_click=rx.redirect(f'/comment_editor/{CommentsPageState.reckoning_id}/{c.id}'),
                    ),
                    # no_edit_button(
                    #     height="15%",
                    #     width="15%",
                    # ),
                ),
                rx.cond(
                    ((CommentsPageState.user.role > 0) | ((c.user_id == CommentsPageState.user.id) & (c.supports == 0) & (c.detracts == 0) & (c.points_of_order == 0))),
                    delete_button(
                        height="15%",
                        width="15%",
                        on_click=CommentsPageState.delete_reckoning(c.id),
                    ),
                    # no_delete_button(
                    #     height="15%",
                    #     width="15%",
                    # ),
                ),
                view_children_button(
                    height="15%",
                    width="15%",
                    on_click=rx.redirect(f"/comments/{c.id}"),
                ),
                grid_template_columns="0.25fr 0.5fr 0.25fr 5fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr",
                py=1,
                px=1,
                gap=1,
                #auto_columns="auto auto auto 5fr auto auto auto auto auto auto auto",
                **control_panel_text_style,
            ),
        border="1px solid #ededed",
        border_radius="10px",
        padding=2,
        gap=2,
        mt=2,
    )


def feed_header():
    """The header of the feed."""
    return rx.grid(
        rx.input(on_change=CommentsPageState.set_search, placeholder="Search history", **input_style_focus),
        rx.grid(
            rx.text_area(default_value=CommentsPageState.parent.content, is_read_only=True, width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em"),
            rx.cond(
                CommentsPageState.parent.parent_reckoning_id,
                view_parent_button(
                    on_click=rx.redirect(f"/comments/{CommentsPageState.parent.parent_reckoning_id}"),
                    height="15%",
                    width="15%",
                ),
                view_parent_button(
                    on_click=rx.redirect(f"/concept/{CommentsPageState.parent.id}"),
                    height="15%",
                    width="15%",
                ),
            ),
            support_comment_button(
                height="15%",
                width="15%",
                on_click=rx.redirect(f'/new_comment_on_parent_editor/{CommentsPageState.reckoning_id}/{CommentsPageState.reckoning_id}/{ReckoningTypes.support}'),
            ),
            poo_comment_button(
                height="15%",
                width="15%",
                on_click=rx.redirect(f'/new_comment_on_parent_editor/{CommentsPageState.reckoning_id}/{CommentsPageState.reckoning_id}/{ReckoningTypes.point_of_order}'),
            ),
            detract_from_comment_button(
                height="15%",
                width="15%",
                on_click=rx.redirect(f'/new_comment_on_parent_editor/{CommentsPageState.reckoning_id}/{CommentsPageState.reckoning_id}/{ReckoningTypes.detract}'),
            ),
            grid_template_columns="10fr 1fr 1fr 1fr 1fr",
            py=2,
            px=2,
            border_bottom="1px solid #ededed",
            **control_panel_text_style,
        ),
        grid_template_columns="1fr",
        py=2,
        px=2,
        border_bottom="1px solid #ededed",
        **control_panel_text_style,
    )


def feed():
    """The feed."""
    return rx.box(
        rx.foreach(
            CommentsPageState.comments,
            render_comment,
        ),
        reckoning_feedback_modal(),
        #border_x="1px solid #ededed",
        h="100%",
    )


@rx.page(route="/comments/[rid]", on_load=CommentsPageState.on_load, **page_params)
def comments():
    """The comments page."""
    return container(
        navbar(feed_header()),
        rx.grid(
            feed(),
            grid_template_columns="1fr",
            h="100vh",
            gap=4,
        ),
        max_width="1300px",
    )
