"""The your reckonings page."""
import reflex as rx
from sqlmodel import select, delete
from sqlalchemy import and_ as _and
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.styles import input_style, page_params, control_panel_text_style
from ..components import container
from ..components import navbar
from reckon.components.buttons import support_concept_button, detract_from_concept_button, provide_feedback_on_concept_button, view_children_button, compare_concepts_button, delete_button, support_comment_button, detract_from_comment_button, poo_comment_button, no_feedback_button, feedback_button, unsupported_concept_button, undetracted_concept_button, edit_button, no_edit_button, no_delete_button
from reckon.components.reckoning_feedback_modal import reckoning_feedback_modal, ReckoningFeedbackModalState

class YourReckoningsPageState(AppState):
    """The state for the your reckonings page."""
    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            if self.search:
                self.reckonings = session.exec(
                    select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.content.contains(self.search), Reckoning.user_id == self.user.id))
                ).unique().all()
            else:
                self.reckonings = session.exec(select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.content != "", Reckoning.user_id == self.user.id))
                ).unique().all()
            for r in self.reckonings:
                r.compute_tallies(self.user.id)

    content: str
    reckonings: list[Reckoning] = []
    search: str

    def compare_concepts(self, concept):
        pass

    def delete_reckoning(self, reckoning):
        """Delete a reckoning."""
        with rx.session() as session:
            session.exec(delete(Reckoning).where(Reckoning.id == reckoning))
            session.commit()
        return self.get_reckonings()
    
    def set_search(self, search):
        """Set the search query."""
        self.search = search
        return self.get_reckonings()
    
    def on_load(self):
        self.check_login()
        self.get_reckonings()

def feed_header():
    """The header of the feed."""
    return rx.hstack(
        rx.input(on_change=YourReckoningsPageState.set_search, placeholder="Search history", **input_style),
        justify="space-between",
        p=4,
        border_bottom="1px solid #ededed",
    )

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
                    on_click=rx.redirect(f'/new_comment_editor/{c.parent_reckoning_id}/{c.id}/{ReckoningTypes.support}')
                ),
                poo_comment_button(
                    height="15%",
                    width="15%",
                    on_click=rx.redirect(f'/new_comment_editor/{c.parent_reckoning_id}/{c.id}/{ReckoningTypes.point_of_order}')
                ),
                detract_from_comment_button(
                    height="15%",
                    width="15%",
                    on_click=rx.redirect(f'/new_comment_editor/{c.parent_reckoning_id}/{c.id}/{ReckoningTypes.detract}')
                ),
                feedback_button(
                    height="15%",
                    width="15%",
                    on_click=ReckoningFeedbackModalState.visible,
                ),
                rx.cond(
                    (c.user_id == YourReckoningsPageState.user.id),
                    edit_button(
                        height="15%",
                        width="15%",
                        on_click=rx.redirect(f'/comment_editor/{c.parent_reckoning_id}/{c.id}'),
                    ),
                    no_edit_button(
                        height="15%",
                        width="15%",
                    ),
                ),
                rx.cond(
                    (c.user_id == YourReckoningsPageState.user.id),
                    delete_button(
                        height="15%",
                        width="15%",
                        on_click=YourReckoningsPageState.delete_reckoning(c.id),
                    ),
                    no_delete_button(
                        height="15%",
                        width="15%",
                    ),
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
        key=c.id,
        border="1px solid #ededed",
        border_radius="10px",
        padding=2,
        gap=2,
        mt=2,
    )

def render_concept(c: Reckoning):
    """Display for an individual concept in the feed."""
    return rx.box (
            rx.grid(
                rx.text_area(default_value=c.content, is_read_only=True, width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em"),
                rx.grid(
                    rx.text(c.supports_detracts_ratio),
                    rx.spacer(),
                    rx.cond(
                        (c.user_vote_history == 0) & (c.user_id != YourReckoningsPageState.user.id),
                        rx.fragment(
                            unsupported_concept_button (
                                height="15%",
                                width="15%",
                                on_click=rx.redirect(f'/new_comment_editor/{c.id}/{c.id}/{ReckoningTypes.support}'),
                            ),
                            undetracted_concept_button(
                                height="15%",
                                width="15%",
                                on_click=rx.redirect(f'/new_comment_editor/{c.id}/{c.id}/{ReckoningTypes.detract}'),
                            )
                        ),
                        None
                    ),
                    rx.cond(
                        (c.user_vote_history == 1) | (c.user_id == YourReckoningsPageState.user.id),
                        rx.fragment(
                            support_concept_button (
                                height="15%",
                                width="15%",
                            ),
                            undetracted_concept_button (
                                height="15%",
                                width="15%",
                            ),
                        ),
                        None
                    ),
                    rx.cond(
                        (c.user_vote_history == 2),
                        rx.fragment(
                            unsupported_concept_button(
                                height="15%",
                                width="15%",
                            ),
                            detract_from_concept_button(
                                height="15%",
                                width="15%",
                            ),
                        ),
                        None
                    ),
                    provide_feedback_on_concept_button(
                        height="15%",
                        width="15%",
                        on_click=ReckoningFeedbackModalState.visible,
                    ),
                    compare_concepts_button(
                        height="15%",
                        width="15%",
                        on_click=YourReckoningsPageState.compare_concepts(c.id),
                    ),
                    edit_button(
                        height="15%",
                        width="15%",
                        on_click=rx.redirect(f'/concept_editor/{c.id}'),#on_click=rx.redirect(f'/concept_editor/{YourReckoningsPageState.concept_id}')
                    ),
                    delete_button(
                        height="15%",
                        width="15%",
                        on_click=YourReckoningsPageState.delete_reckoning(c.id),
                    ),
                    view_children_button(
                        height="15%",
                        width="15%",
                        on_click=rx.redirect(f"/comments/{c.id}"),
                    ),
                    grid_template_columns="1fr 5fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr",
                    py=1,
                    px=1,
                    gap=1,
                    **control_panel_text_style,
                ),
                py=2,
                px=2,
                gap=2,
            ),
            key=c.id,
            border="1px solid #ededed",
            border_radius="10px",
            padding=2,
            gap=4,
            mt=2
        )

def reckoning(r: Reckoning):
    return rx.cond(
        r.type,
        render_comment(r),
        render_concept(r),
    )

def feed():
    """The feed."""
    return rx.box(
        feed_header(),
        rx.foreach(
            YourReckoningsPageState.reckonings,
            reckoning,
        ),
        reckoning_feedback_modal(),
        #border_x="1px solid #ededed",
        h="100%",
    )

@rx.page(route="/your_reckonings", on_load=YourReckoningsPageState.on_load, **page_params)
def your_reckonings():
    """The your history page."""
    return container(
        navbar(),
        rx.grid(
            feed(),
            grid_template_columns="1fr",
            h="100vh",
            gap=4,
        ),
        max_width="1300px",
    )
