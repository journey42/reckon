"""The compare page."""
import reflex as rx
from sqlmodel import select, delete
from sqlalchemy import and_ as _and
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.styles import input_style, page_params, control_panel_text_style
from ..components import container
from ..components import navbar
from reckon.components.buttons import support_concept_button, detract_from_concept_button, provide_feedback_on_concept_button, view_children_button, compare_concepts_button, delete_button, support_comment_button, detract_from_comment_button, poo_comment_button, no_feedback_button, feedback_button, unsupported_concept_button, undetracted_concept_button, edit_button, no_edit_button, no_delete_button
from reckon.components.reckoning_feedback_modal import reckoning_feedback_modal, ReckoningFeedbackModalState
from reckon.utils.db import find_similar_texts_with_join

class ComparePageState(AppState):

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        # with rx.session() as session:
        #     print("Search", self.search)
        #     if self.search:
        #         self.reckonings = session.exec(
        #             select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.content.contains(self.search), Reckoning.type == ReckoningTypes.concept))
        #         ).all()
        #     else:
        #         self.reckonings = session.exec(
        #             select(Reckoning).order_by(Reckoning.created_at.desc()).where(Reckoning.type == ReckoningTypes.concept)
        #         ).all()
        primary_keys = []
        with rx.session() as session:
            session.expire_on_commit = False
            concept = self.reckonings = session.exec(
                select(Reckoning)
                .where(
                    Reckoning.id == self.reckoning_id
                )
            ).one_or_none()
            print(concept.content)
            primary_keys, results = find_similar_texts_with_join(concept.id, 0.75, 10)
        
        with rx.session() as session:
            session.expire_on_commit = False
            print("Search", self.search)
            if self.search:
                # Assuming `primary_keys` is your list of IDs to filter by
                self.reckonings = session.exec(
                    select(Reckoning)
                    .where(
                        _and(
                            Reckoning.content.contains(self.search),
                            Reckoning.id.in_(primary_keys)  # Filtering by a list of primary keys
                        )
                    )
                ).all()
            else:
                self.reckonings = session.exec(
                    select(Reckoning)
                    .where(
                            Reckoning.id.in_(primary_keys)  # Filtering by a list of primary keys
                    )
                ).all()

            # Creating a mapping of ID to reckoning for fast lookup
            id_to_reckoning = {reckoning.id: reckoning for reckoning in self.reckonings}

            # Ordering the reckonings in Python according to the order of IDs in primary_keys
            ordered_reckonings = [id_to_reckoning[id] for id in primary_keys if id in id_to_reckoning]

            # Now ordered_reckonings contains your objects in the order of primary_keys
            self.reckonings = ordered_reckonings

            results_dict = dict(results)

            for r in self.reckonings:
                r.similarity = results_dict[r.id]
                print("\n")
                r.compute_tallies(self.user.id)
                print(r)
        
        #yield ComparePageState.reload_reckonings

    content: str
    reckonings: list[Reckoning]
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

    @rx.var
    def reckoning_id(self) -> str:
        return self.router.page.params.get('rid', 'no rid')


def feed_header():
    """The header of the feed."""
    return rx.hstack(
        rx.input(on_change=ComparePageState.set_search, placeholder="Search concepts", **input_style),
        justify="space-between",
        p=4,
        border_bottom="1px solid #ededed",
    )

def render_concept(c: Reckoning):
    """Display for an individual concept in the feed."""
    return rx.box (
            rx.grid(
                rx.text_area(default_value=c.content, is_read_only=True, width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em"),
                rx.grid(
                    rx.text(c.supports_detracts_ratio),
                    rx.spacer(),
                    rx.text(c.similarity),
                    rx.spacer(),
                    rx.cond(
                        (c.user_vote_history == 0) & (c.user_id != ComparePageState.user.id),
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
                        (c.user_vote_history == 1) | (c.user_id == ComparePageState.user.id),
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
                        on_click=ComparePageState.compare_concepts(c.id),
                    ),
                    rx.cond(
                        (c.user_id == ComparePageState.user.id),
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
                        (c.user_id == ComparePageState.user.id),
                        delete_button(
                            height="15%",
                            width="15%",
                            on_click=ComparePageState.delete_reckoning(c.id),
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
                    grid_template_columns="2fr 2fr 1fr 5fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr",
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

def feed():
    """The feed."""
    return rx.box(
        feed_header(),
        rx.foreach(
            ComparePageState.reckonings,
            render_concept,
        ),
        #rx.text(ComparePageState.reckonings.to_string()),
        reckoning_feedback_modal(),
        #border_x="1px solid #ededed",
        h="100%",
    )


@rx.page(route="/compare/[rid]", on_load=ComparePageState.on_load, **page_params)
def compare():
    """The new concepts page."""
    return container(
        # rx.cond(ComparePageState.refreshPage, rx.script("location.reload()")),
        navbar(),
        rx.grid(
            feed(),
            grid_template_columns="1fr",
            h="100vh",
            gap=4,
        ),
        max_width="1300px",
    )
