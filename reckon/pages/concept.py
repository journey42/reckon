"""The concept page."""
import reflex as rx
from reckon.styles import page_params, control_panel_text_style
from ..components import container
from ..components import navbar
from reckon.components.buttons import view_children_button, compare_concepts_button, edit_button, delete_button, support_concept_button, detract_from_concept_button, provide_feedback_on_concept_button, unsupported_concept_button, undetracted_concept_button, no_edit_button, no_delete_button
from reckon.components.reckoning_feedback_modal import reckoning_feedback_modal, ReckoningFeedbackModalState
from sqlmodel import select, delete
from reckon.state.base import AppState, Reckoning, ReckoningTypes

class ConceptPageState(AppState):
    """The state for the concept page."""

    concept: Reckoning = None

    def get_concept(self, cid):
        """Get concept with id of cid from the database."""
        with rx.session() as session:
                self.concept = session.exec(select(Reckoning).where(Reckoning.id == cid)).first()
                self.concept.compute_tallies(self.user.id)

    def compare_concepts(self, concept):
        pass

    def delete_reckoning(self, rid):
        """Delete a reckoning."""
        with rx.session() as session:
            session.exec(delete(Reckoning).where(Reckoning.id == rid))
            session.commit()
        return rx.redirect(f"/home")
    
    def on_load(self):
        self.check_login()
        self.get_concept(self.concept_id)

    @rx.var
    def concept_id(self) -> str:
        return self.router.page.params.get('rid', 'no rid')

def render_concept(c: Reckoning):
    """Display for an individual concept in the feed."""
    return rx.box (
            rx.grid(
                rx.text_area(default_value=c.content, on_click=rx.redirect(f'/concept_editor/{ConceptPageState.concept_id}'), is_read_only=True, width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em"),
                rx.grid(
                    rx.text(c.supports_detracts_ratio),
                    rx.spacer(),
                    rx.cond(
                        (c.user_vote_history == 0) & (c.user_id != ConceptPageState.user.id),
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
                        (c.user_vote_history == 1) | (c.user_id == ConceptPageState.user.id),
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
                        on_click=ConceptPageState.compare_concepts(c.id),
                    ),
                    rx.cond(
                        (c.user_id == ConceptPageState.user.id),
                        edit_button(
                            height="15%",
                            width="15%",
                            on_click=rx.redirect(f'/concept_editor/{ConceptPageState.concept_id}'),
                        ),
                        no_edit_button(
                            height="15%",
                            width="15%",
                        ),
                    ),
                    rx.cond(
                        (c.user_id == ConceptPageState.user.id),
                        delete_button(
                            height="15%",
                            width="15%",
                            on_click=ConceptPageState.delete_reckoning(c.id),
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
        render_concept(ConceptPageState.concept),
        reckoning_feedback_modal(),
        #border_x="1px solid #ededed",
        h="100%",
    )


@rx.page(route="/concept/[rid]", on_load=ConceptPageState.on_load, **page_params)
def concept():
    """The concept page."""
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
