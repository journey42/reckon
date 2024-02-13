"""The trending concepts page."""
import reflex as rx
from sqlmodel import select, func, delete
from sqlalchemy import and_ as _and
from sqlalchemy.orm import aliased
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.styles import input_style, page_params, control_panel_text_style
from ..components import container
from ..components import navbar
from reckon.components.buttons import support_concept_button, detract_from_concept_button, provide_feedback_on_concept_button, view_children_button, compare_concepts_button, delete_button, support_comment_button, detract_from_comment_button, poo_comment_button, no_feedback_button, feedback_button, unsupported_concept_button, undetracted_concept_button, edit_button, no_edit_button, no_delete_button
from reckon.components.reckoning_feedback_modal import reckoning_feedback_modal, ReckoningFeedbackModalState

class TrendingConceptsPageState(AppState):
    """The state for the trending concept page."""
    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            if self.search:
                self.reckonings = session.exec(
                    select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.content.contains(self.search), Reckoning.type == ReckoningTypes.concept))
                ).unique().all()
            else:

                # Create an alias for child reckonings to differentiate from parent reckonings in the self-join
                ChildReckoning = aliased(Reckoning)

                # Subquery to count the number of "support" type child reckonings for each parent
                supports_count_subquery = (
                    select(
                        ChildReckoning.parent_reckoning_id,
                        func.count(ChildReckoning.id).label('supports_count')
                    )
                    .where(ChildReckoning.type == ReckoningTypes.support)
                    .group_by(ChildReckoning.parent_reckoning_id)
                    .subquery()
                )

                # Main query to select reckonings and the count of their supports, ordered by the count of supports
                statement = (
                    select(
                        Reckoning,
                        supports_count_subquery.c.supports_count
                    )
                    .outerjoin(supports_count_subquery, Reckoning.id == supports_count_subquery.c.parent_reckoning_id)
                    .where(Reckoning.type == ReckoningTypes.concept)  # Adjust as needed to filter by specific reckoning types
                    .order_by(supports_count_subquery.c.supports_count.asc(), Reckoning.created_at.desc())
                )
                
                # Execute the query and fetch all results
                results = session.exec(statement).unique().all()

                # Extract Reckoning objects from the results
                self.reckonings = [result[0] for result in results]

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
        yield self.check_login()
        yield self.get_reckonings()


def feed_header():
    """The header of the feed."""
    return rx.hstack(
        rx.input(on_change=TrendingConceptsPageState.set_search, placeholder="Search concepts", **input_style),
        justify="space-between",
        p=4,
        border_bottom="1px solid #ededed",
    )

def render_concept(c: Reckoning):
    """Display for an individual concept in the feed."""
    return rx.box (
            rx.grid(
                rx.text_area(default_value=c.content, on_click=rx.redirect(f'/concept_editor/{c.id}'), is_read_only=True, width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em"),
                rx.grid(
                    rx.text(c.supports_detracts_ratio),
                    rx.spacer(),
                    rx.cond(
                        (c.user_vote_history == 0) & (c.user_id != TrendingConceptsPageState.user.id),
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
                        (c.user_vote_history == 1) | (c.user_id == TrendingConceptsPageState.user.id),
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
                        on_click=TrendingConceptsPageState.compare_concepts(c.id),
                    ),
                    rx.cond(
                        (c.user_id == TrendingConceptsPageState.user.id),
                        edit_button(
                            height="15%",
                            width="15%",
                            on_click=rx.redirect(f'/concept_editor/{c.id}'),
                        ),
                        no_edit_button(
                            height="15%",
                            width="15%",
                        ),
                    ),
                    rx.cond(
                        (c.user_id == TrendingConceptsPageState.user.id),
                        delete_button(
                            height="15%",
                            width="15%",
                            on_click=TrendingConceptsPageState.delete_reckoning(c.id),
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
            border="1px solid #ededed",
            border_radius="10px",
            padding=2,
            gap=4,
            mt=2
        )

def feed():
    """The feed."""
    return rx.box(
        feed_header(),
        rx.foreach(
            TrendingConceptsPageState.reckonings,
            render_concept,
        ),
        reckoning_feedback_modal(),
        #border_x="1px solid #ededed",
        h="100%",
    )

@rx.page(route="/trending_concepts", on_load=TrendingConceptsPageState.on_load, **page_params)
def trending_concepts():
    """The trending concepts page."""
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
