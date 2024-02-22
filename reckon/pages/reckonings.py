"""The your reckonings page."""
import reflex as rx
from datetime import datetime
from sqlmodel import select, delete, func
from sqlalchemy.orm import aliased
from sqlalchemy import and_ as _and
from sqlalchemy import or_ as _or
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.styles import input_style, page_params, control_panel_text_style, input_style_focus, read_only_text_style
from ..components import container
from ..components import navbar
from reckon.components.buttons import up_vote_concept_button, down_vote_concept_button, feedback_button, view_comments_button, compare_concepts_button, delete_button, support_comment_button, detract_from_comment_button, poo_comment_button, no_feedback_button, feedback_button, no_up_vote_concept_button, no_down_vote_concept_button, edit_button, view_concept_button, view_parent_comment_button
from reckon.components.feedback_modal import feedback_modal, FeedbackModalState, reckoning_feedback_options
from reckon.components.concept_modal import concept_modal, ConceptModalState
from reckon.components.comment_modal import comment_modal, CommentModalState
from reckon.utils.db import find_similar_texts_with_join


class ReckoningsPageState(AppState):
    reckonings: list[Reckoning] = []
    search: str
    page_type: int = 0
    rerender: bool = False

    def new_comment(self, subject, type, pid):
        yield CommentModalState.new_comment(subject, type, pid)
        yield CommentModalState.visible()
    
    def edit_comment(self, pid, type, cid, content):
        yield CommentModalState.edit_comment(pid, type, cid, content)
        yield CommentModalState.visible()

    def edit_concept(self, cid):
        yield ConceptModalState.set_concept(cid)
        yield ConceptModalState.visible()

    def provide_feedback_on_reckoning(self, rid):
        yield FeedbackModalState.set_reckoning(rid)
        yield FeedbackModalState.visible()

    def close_modal(self):
        pass

    def compare_concepts(self, cid):
        return rx.redirect(f"/compare/{cid}")
    
    def view_comments(self, cid):
        return rx.redirect(f"/comments/{cid}")
    
    def trigger_rerender(self):
        self.rerender = not (self.rerender)
    
    def vote_on_concept(self, cid, type):
        with rx.session() as session:
            session.expire_on_commit = False
            concept = session.exec(select(Reckoning).where(Reckoning.id == cid)).first()
            vote = session.exec(select(Reckoning).where(_and(Reckoning.parent_reckoning_id == cid, _or(Reckoning.type == ReckoningTypes.up_vote,Reckoning.type == ReckoningTypes.down_vote)))).first()
            if vote:
                if vote.type == type:
                    session.delete(vote)
                else:
                    vote.type = type
                session.commit()
                #yield ReckoningsPageState.trigger_rerender()
                return rx.redirect(self.router.page.path)
            else:
                if concept.user_id == self.user.id:
                    concept.type = ReckoningTypes.concept
                comment = Reckoning(content="n/a", parent_reckoning_id=cid, type=type, created_at=datetime.utcnow(), updated_at=datetime.utcnow(), user_id=self.user.id)
                session.add(comment)
                session.commit()
                return rx.redirect(f"/comments/{cid}")
                
    

class YourDraftsPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

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
        self.page_type = 1
        self.check_login()
        self.get_reckonings()

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            if self.search:
                self.reckonings = session.exec(
                    select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.content.contains(self.search), _and(Reckoning.user_id == self.user.id, Reckoning.type == ReckoningTypes.draft)))
                ).unique().all()
            else:
                self.reckonings = session.exec(select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.type == ReckoningTypes.draft, Reckoning.user_id == self.user.id))
                ).unique().all()
            for r in self.reckonings:
                r.compute_tallies(self.user.id)

class NewConceptsPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

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
        self.page_type = 2
        self.check_login()
        self.get_reckonings()

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            if self.search:
                self.reckonings = session.exec(
                    select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.content.contains(self.search), _or(Reckoning.type == ReckoningTypes.concept, Reckoning.type == ReckoningTypes.draft)))
                ).all()
            else:
                self.reckonings = session.exec(
                    select(Reckoning).order_by(Reckoning.created_at.desc()).where(_or(Reckoning.type == ReckoningTypes.concept, Reckoning.type == ReckoningTypes.draft))
                ).all()
            
            for r in self.reckonings:
                r.compute_tallies(self.user.id)

class TrendingConceptsPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

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
        self.page_type = 3
        self.check_login()
        self.get_reckonings()


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

                # Subquery to count the number of "up_vote" type child reckonings for each parent
                up_vote_count_subquery = (
                    select(
                        ChildReckoning.parent_reckoning_id,
                        func.count(ChildReckoning.id).label('up_vote_count')
                    )
                    .where(ChildReckoning.type == ReckoningTypes.up_vote)
                    .group_by(ChildReckoning.parent_reckoning_id)
                    .subquery()
                )

                # Main query to select reckonings and the count of their up_votes, ordered by the count of upvotes
                statement = (
                    select(
                        Reckoning,
                        up_vote_count_subquery.c.up_vote_count
                    )
                    .outerjoin(up_vote_count_subquery, Reckoning.id == up_vote_count_subquery.c.parent_reckoning_id)
                    .where(Reckoning.type == ReckoningTypes.concept)  # Adjust as needed to filter by specific reckoning types
                    .order_by(up_vote_count_subquery.c.up_vote_count.desc(), Reckoning.created_at.desc())
                )
                
                # Execute the query and fetch all results
                results = session.exec(statement).unique().all()

                # Extract Reckoning objects from the results
                self.reckonings = [result[0] for result in results]

            for r in self.reckonings:
                r.compute_tallies(self.user.id)

class YourReckoningsPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

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
        self.page_type = 4
        self.check_login()
        self.get_reckonings()

    """The state for the your reckonings page."""
    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            if self.search:
                self.reckonings = session.exec(
                    select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.content.contains(self.search), _and(Reckoning.type != ReckoningTypes.concept, _and(Reckoning.user_id == self.user.id, Reckoning.type != ReckoningTypes.draft))))
                ).unique().all()
            else:
                self.reckonings = session.exec(select(Reckoning).order_by(Reckoning.created_at.desc()).where(_and(Reckoning.type != ReckoningTypes.concept, _and(Reckoning.user_id == self.user.id, Reckoning.type != ReckoningTypes.draft)))
                ).unique().all()
            for r in self.reckonings:
                r.cache_parent_details(self.user.id)
                r.compute_tallies(self.user.id)


class ComparePageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

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
        self.page_type = 5
        self.check_login()
        self.get_reckonings()

    @rx.var
    def reckoning_id(self) -> str:
        return self.router.page.params.get('rid', 'no rid')
    
    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        primary_keys = []
        with rx.session() as session:
            session.expire_on_commit = False
            concept = self.reckonings = session.exec(
                select(Reckoning)
                .where(
                    Reckoning.id == self.reckoning_id
                )
            ).one_or_none()
            # print(concept.content)
            primary_keys, results = find_similar_texts_with_join(concept.id, 0.75, 10)
            # print(primary_keys)
            # print(results)
        
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
                r.similarity = round(((results_dict[r.id]-1)*-1),2) #((round(results_dict[r.id] - 1), 2) * -1)
                r.compute_tallies(self.user.id)

class ConceptPageState(ReckoningsPageState):
    """The state for the comment page."""
    def close_complete_modal(self):
        yield self.get_reckonings()

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
        self.page_type = 6
        self.check_login()
        self.get_reckonings()

    def get_reckonings(self):
        """Get reckoning with rid of cid from the database."""
        with rx.session() as session:
                self.reckonings = [session.exec(select(Reckoning).where(Reckoning.id == self.concept_id)).first()]
                for r in self.reckonings:
                    r.compute_tallies(self.user.id)

    @rx.var
    def concept_id(self) -> str:
        return self.router.page.params.get('rid', 'no rid')
    

class CommentsPageState(ReckoningsPageState):
    """The state for the comments page."""
    parent: Reckoning = None

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning."""
        with rx.session() as session:
            session.exec(delete(Reckoning).where(Reckoning.id == rid))
            session.commit()
        return self.get_reckonings()
    
    def set_search(self, search):
        """Set the search query."""
        self.search = search
        return self.get_reckonings()
    
    def on_load(self):
        self.page_type = 7
        self.check_login()
        self.get_reckonings()

    def get_reckonings(self):
        """Get comments for this reckoning from the database."""
        with rx.session() as session:
            self.parent = session.exec(select(Reckoning).where(Reckoning.id == self.reckoning_id)).first()
            self.parent.compute_tallies(self.user.id)

            if self.search:
                self.reckonings = session.exec(
                    select(Reckoning).order_by(Reckoning.created_at.asc()).where(_and(
                        Reckoning.content.contains(self.search),
                        Reckoning.content != "",
                        Reckoning.parent_reckoning_id == self.reckoning_id,
                        _or(
                            Reckoning.type == ReckoningTypes.support,
                            Reckoning.type == ReckoningTypes.detract,
                            Reckoning.type == ReckoningTypes.point_of_order
                        )
                    )
                )).unique().all()
            else:
                self.reckonings = session.exec(select(Reckoning).order_by(Reckoning.created_at.asc()).where(
                    _and(
                        Reckoning.content != "",
                        Reckoning.parent_reckoning_id == self.reckoning_id,
                        _or(
                            Reckoning.type == ReckoningTypes.support,
                            Reckoning.type == ReckoningTypes.detract,
                            Reckoning.type == ReckoningTypes.point_of_order
                        )
                    )
                )).unique().all()

            for r in self.reckonings:
                r.compute_tallies(self.user.id)

    @rx.var
    def reckoning_id(self) -> str:
        return self.router.page.params.get('rid', 'no rid')
    

def parent_reckoning(state):
    """The parent reckoning component."""
    return rx.grid(
        rx.input(on_change=state.set_search, placeholder="Search comments", **input_style_focus),
        rx.grid(
            rx.grid(
                rx.cond(
                    state.parent.parent_reckoning_id,
                    view_parent_comment_button(
                        height="15%",
                        width="15%",
                        on_click=rx.redirect(f"/comments/{state.parent.parent_reckoning_id}"),
                    ),
                    compare_concepts_button(
                        on_click=rx.redirect(f"/compare/{state.parent.id}"),
                        height="15%",
                        width="15%",
                    ),
                ),
                rx.cond(
                    (state.parent.user_id != state.user.id),
                    feedback_button(
                        height="15%",
                        width="15%",
                        on_click=state.provide_feedback_on_reckoning(state.parent.id),
                    ),
                    rx.spacer()
                ),
                py=2,
                px=2,
                gap=2,
                place_items="center",
            ),
            rx.text_area(key=state.parent.id, default_value=state.parent.content, **read_only_text_style),
            grid_template_columns="1fr 12fr",
            py=2,
            px=2,
            gap=1,
            # border_bottom="1px solid #ededed",
            **control_panel_text_style,
        ),
        rx.grid(
            rx.spacer(),
            rx.cond(
                (state.parent.type == 0),
                rx.fragment(
                rx.cond(
                        (state.parent.user_vote_history == ReckoningTypes.no_vote), #& (state.parent.user_id != state.user.id),
                        rx.fragment(
                            no_up_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(state.parent.id, ReckoningTypes.up_vote)
                            ),
                            rx.text(state.parent.up_votes),
                            no_down_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(state.parent.id, ReckoningTypes.down_vote)
                            ),
                            rx.text(state.parent.down_votes),
                        ),
                        None
                    ),
                    rx.cond(
                        (state.parent.user_vote_history == ReckoningTypes.up_vote), #| (state.parent.user_id == state.user.id),
                        rx.fragment(
                            up_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(state.parent.id, ReckoningTypes.up_vote)
                            ),
                            rx.text(state.parent.up_votes),
                            no_down_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(state.parent.id, ReckoningTypes.down_vote)
                            ),
                            rx.text(state.parent.down_votes),
                        ),
                        None
                    ),
                    rx.cond(
                        (state.parent.user_vote_history == ReckoningTypes.down_vote),
                        rx.fragment(
                            no_up_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(state.parent.id, ReckoningTypes.up_vote)
                            ),
                            rx.text(state.parent.up_votes),
                            down_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(state.parent.id, ReckoningTypes.down_vote)
                            ),
                            rx.text(state.parent.down_votes),
                        ),
                        None
                    ),
                ),
                rx.fragment(
                    rx.spacer(),
                    rx.spacer(),
                    rx.spacer(),
                    rx.spacer(),
                ),
            ),
            support_comment_button(
                height="15%",
                width="15%",
                on_click=state.new_comment(state.parent.content, ReckoningTypes.support, state.reckoning_id)
            ),
            # rx.text(state.parent.supports),
            poo_comment_button(
                height="15%",
                width="15%",
                on_click=state.new_comment(state.parent.content, ReckoningTypes.point_of_order, state.reckoning_id)
            ),
            # rx.text(state.parent.points_of_order),
            detract_from_comment_button(
                height="15%",
                width="15%",
                on_click=state.new_comment(state.parent.content, ReckoningTypes.detract, state.reckoning_id)
            ),
            # rx.text(state.parent.detracts),
            grid_template_columns="10fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr",
            py=2,
            px=2,
            gap=1,
            # border_bottom="1px solid #ededed",
            **control_panel_text_style,
        ),
        grid_template_columns="1fr",
        py=2,
        px=2,
        border_bottom="1px solid #ededed",
        **control_panel_text_style,
    )

def search(state):
    """The search component of the navbar."""
    return rx.hstack(
        rx.input(on_change=state.set_search, placeholder="Search reckonings", **input_style),
        justify="space-between",
        p=4,
        # border_bottom="1px solid #ededed",
    )

def render_comment(state, c: Reckoning):
    """Display for an individual comment in the feed."""
    return rx.grid(
        rx.grid(
            rx.cond(
                (state.page_type == 4),
                rx.cond(
                    (c.parent_type == 0),
                    rx.grid(
                        rx.text(c.parent_content, **read_only_text_style),
                        rx.cond(
                            (c.parent_user_vote_history == ReckoningTypes.no_vote), #& (c.user_id != state.user.id),
                            rx.fragment(
                                no_up_vote_concept_button (
                                    height="15%",
                                    width="15%",
                                    on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.up_vote)
                                ),
                                rx.text(c.parent_reckoning.up_votes),
                                no_down_vote_concept_button(
                                    height="15%",
                                    width="15%",
                                    on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.down_vote)
                                ),
                                rx.text(c.parent_down_votes),
                            ),
                            None
                        ),
                        rx.cond(
                            (c.parent_user_vote_history == ReckoningTypes.up_vote), #| (c.user_id == state.user.id),
                            rx.fragment(
                                up_vote_concept_button (
                                    height="15%",
                                    width="15%",
                                    on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.up_vote)
                                ),
                                rx.text(c.parent_up_votes),
                                no_down_vote_concept_button (
                                    height="15%",
                                    width="15%",
                                    on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.down_vote)
                                ),
                                rx.text(c.parent_down_votes),
                            ),
                            None
                        ),
                        rx.cond(
                            (c.parent_user_vote_history == ReckoningTypes.down_vote),
                            rx.fragment(
                                no_up_vote_concept_button(
                                    height="15%",
                                    width="15%",
                                    on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.up_vote)
                                ),
                                rx.text(c.parent_reckoning.up_votes),
                                down_vote_concept_button(
                                    height="15%",
                                    width="15%",
                                    on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.down_vote)
                                ),
                                rx.text(c.parent_down_votes),
                            ),
                            None
                        ),
                        view_parent_comment_button(
                            height="15%",
                            width="15%",
                            on_click=rx.redirect(f"/comments/{c.parent_id}"),
                        ),
                        grid_template_columns="9fr 1fr 1fr 1fr 1fr 1fr",
                        py=1,
                        px=1,
                        gap=1,
                        **control_panel_text_style,
                    ),
                    rx.grid(
                        rx.text(c.parent_content, **read_only_text_style),
                        rx.match(
                            c.parent_type,
                            (ReckoningTypes.support, support_comment_button(height="15%", width="15%")),
                            (ReckoningTypes.detract, detract_from_comment_button(height="15%", width="15%")),
                            (ReckoningTypes.point_of_order, poo_comment_button(height="15%", width="15%")),
                        ),
                        view_parent_comment_button(
                            height="15%",
                            width="15%",
                            on_click=rx.redirect(f"/comments/{c.parent_reckoning_id}"),
                        ),
                        grid_template_columns="12fr 1fr 1fr",
                        py=1,
                        px=1,
                        gap=1,
                        **control_panel_text_style,
                    ),

                ),
                None
            ),
            rx.grid(
                rx.text(c.content, **read_only_text_style),
                rx.match(
                    c.type,
                    (ReckoningTypes.support, support_comment_button(height="15%", width="15%")),
                    (ReckoningTypes.detract, detract_from_comment_button(height="15%", width="15%")),
                    (ReckoningTypes.point_of_order, poo_comment_button(height="15%", width="15%")),
                ),
                view_comments_button(
                    height="15%",
                    width="15%",
                    on_click=state.view_comments(c.id),
                ),
                grid_template_columns="12fr 1fr 1fr",
                py=1,
                px=1,
                gap=1,
                **control_panel_text_style,
            ),
            rx.grid (
                    rx.cond(
                        ((state.user.role > 0) | ((c.user_id == state.user.id) & (c.supports == 0) & (c.detracts == 0) & (c.points_of_order == 0))),
                        edit_button(
                            height="15%",
                            width="15%",
                            on_click=state.edit_comment(c.parent_reckoning_id, c.type, c.id, c.content)
                        ),
                        rx.spacer(),
                    ),
                    rx.cond(
                        ((state.user.role > 0) | ((c.user_id == state.user.id) & (c.supports == 0) & (c.detracts == 0) & (c.points_of_order == 0))),
                        delete_button(
                            height="15%",
                            width="15%",
                            on_click=state.delete_reckoning(c.id),
                        ),
                        rx.spacer(),
                    ),
                    rx.spacer(),
                    rx.cond(
                        (c.user_id != state.user.id),
                        feedback_button(
                            height="15%",
                            width="15%",
                            on_click=state.provide_feedback_on_reckoning(c.id),
                        ),
                        rx.spacer(),
                    ),
                    rx.spacer(),
                    support_comment_button(
                        height="15%",
                        width="15%",
                        on_click=state.new_comment(c.content, ReckoningTypes.support, c.id)
                    ),
                    rx.text(c.supports),
                    poo_comment_button(
                        height="15%",
                        width="15%",
                        on_click=state.new_comment(c.content, ReckoningTypes.point_of_order, c.id)
                    ),
                    rx.text(c.points_of_order),
                    detract_from_comment_button(
                        height="15%",
                        width="15%",
                        on_click=state.new_comment(c.content, ReckoningTypes.detract, c.id)
                    ),
                    rx.text(c.detracts),
                    grid_template_columns="1fr 1fr 2fr 1fr 2fr 1fr 1fr 1fr 1fr 1fr 1fr",
                    py=1,
                    px=1,
                    gap=1,
                    **control_panel_text_style,
                ),
                # grid_template_columns="1fr 1fr 1fr",
                py=1,
                px=1,
                gap=1,
                **control_panel_text_style,
            ),
            # grid_template_columns="14fr 1fr",
            border="1px solid #ededed",
            border_radius="10px",
            padding=2,
            gap=2,
            mt=2,
        )


def render_vote(state, c: Reckoning):
    """Display for an individual vote in the feed."""
    return rx.grid(
                rx.grid(
                    compare_concepts_button(
                        height="15%",
                        width="15%",
                        on_click=state.compare_concepts(c.parent_id),
                    ),
                    rx.text( c.parent_content, **read_only_text_style),
                    grid_template_columns="1fr 22fr",
                    py=1,
                    px=1,
                    gap=1,
                    **control_panel_text_style,
                ),
                rx.grid(
                    rx.cond(
                        (state.page_type == 1),
                        edit_button(
                            height="15%",
                            width="15%",
                            on_click=state.edit_concept(c.parent_id),
                        ),
                       rx.spacer(), 
                    ),
                    rx.cond(
                        (state.page_type == 1),
                        delete_button(
                            height="15%",
                            width="15%",
                            on_click=state.delete_reckoning(c.parent_id),
                        ),
                        rx.spacer(),
                    ),
                    rx.spacer(),
                    rx.cond(
                        (state.page_type == 5),
                        rx.text(c.similarity),
                        rx.spacer(),
                    ),
                    rx.spacer(),
                    rx.cond(
                        (c.user_id != state.user.id),
                        feedback_button(
                            height="15%",
                            width="15%",
                            on_click=state.provide_feedback_on_reckoning(c.parent_id),
                        ),
                        rx.spacer()
                    ),
                    rx.spacer(),
                    rx.cond(
                        (c.parent_user_vote_history == ReckoningTypes.no_vote), #& (c.user_id != state.user.id),
                        rx.fragment(
                            no_up_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.up_vote)
                            ),
                            rx.text(c.parent_up_votes),
                            no_down_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.down_vote)
                            ),
                            rx.text(c.parent_down_votes),
                        ),
                        None
                    ),
                    rx.cond(
                        (c.parent_user_vote_history == ReckoningTypes.up_vote), #| (c.user_id == state.user.id),
                        rx.fragment(
                            up_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.up_vote)
                            ),
                            rx.text(c.parent_up_votes),
                            no_down_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.down_vote)
                            ),
                            rx.text(c.parent_down_votes),
                        ),
                        None
                    ),
                    rx.cond(
                        (c.parent_user_vote_history == ReckoningTypes.down_vote),
                        rx.fragment(
                            no_up_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.up_vote)
                            ),
                            rx.text(c.parent_up_votes),
                            down_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.parent_id, ReckoningTypes.down_vote)
                            ),
                            rx.text(c.parent_down_votes),
                        ),
                        None
                    ),
                    rx.spacer(),
                    view_concept_button(
                        height="15%",
                        width="15%",
                        on_click=state.view_comments(c.parent_id),
                    ),
                    rx.cond(
                        (state.rerender),
                        rx.text(c.parent_total_comments),
                        rx.text(c.parent_total_comments),
                    ),
                    grid_template_columns="1fr 1fr 1fr 1fr 8fr 1fr 2fr 1fr 1fr 1fr 1fr 2fr 1fr 1fr",
                    py=1,
                    px=1,
                    gap=1,
                    **control_panel_text_style,
            ),
            border="1px solid #ededed",
            border_radius="10px",
            padding=2,
            gap=4,
            mt=2
        )


def render_concept(state, c: Reckoning):
    """Display for an individual concept in the feed."""
    return rx.grid(
                rx.grid(
                    compare_concepts_button(
                        height="15%",
                        width="15%",
                        on_click=state.compare_concepts(c.id),
                    ),
                    rx.text( c.content, **read_only_text_style),
                    grid_template_columns="1fr 22fr",
                    py=1,
                    px=1,
                    gap=1,
                    **control_panel_text_style,
                ),
                rx.grid(
                    rx.cond(
                        (state.page_type == 1),
                        edit_button(
                            height="15%",
                            width="15%",
                            on_click=state.edit_concept(c.id),
                        ),
                       rx.spacer(), 
                    ),
                    rx.cond(
                        (state.page_type == 1),
                        delete_button(
                            height="15%",
                            width="15%",
                            on_click=state.delete_reckoning(c.id),
                        ),
                        rx.spacer(),
                    ),
                    rx.spacer(),
                    rx.cond(
                        (state.page_type == 5),
                        rx.text(c.similarity),
                        rx.spacer(),
                    ),
                    rx.spacer(),
                    rx.cond(
                        (c.user_id != state.user.id),
                        feedback_button(
                            height="15%",
                            width="15%",
                            on_click=state.provide_feedback_on_reckoning(c.id),
                        ),
                        rx.spacer()
                    ),
                    rx.spacer(),
                    rx.cond(
                        (c.user_vote_history == ReckoningTypes.no_vote), #& (c.user_id != state.user.id),
                        rx.fragment(
                            no_up_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.id, ReckoningTypes.up_vote)
                            ),
                            rx.text(c.up_votes),
                            no_down_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.id, ReckoningTypes.down_vote)
                            ),
                            rx.text(c.down_votes),
                        ),
                        None
                    ),
                    rx.cond(
                        (c.user_vote_history == ReckoningTypes.up_vote), #| (c.user_id == state.user.id),
                        rx.fragment(
                            up_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.id, ReckoningTypes.up_vote)
                            ),
                            rx.text(c.up_votes),
                            no_down_vote_concept_button (
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.id, ReckoningTypes.down_vote)
                            ),
                            rx.text(c.down_votes),
                        ),
                        None
                    ),
                    rx.cond(
                        (c.user_vote_history == ReckoningTypes.down_vote),
                        rx.fragment(
                            no_up_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.id, ReckoningTypes.up_vote)
                            ),
                            rx.text(c.up_votes),
                            down_vote_concept_button(
                                height="15%",
                                width="15%",
                                on_click=state.vote_on_concept(c.id, ReckoningTypes.down_vote)
                            ),
                            rx.text(c.down_votes),
                        ),
                        None
                    ),
                    rx.spacer(),
                    view_concept_button(
                        height="15%",
                        width="15%",
                        on_click=state.view_comments(c.id),
                    ),
                    rx.cond(
                        (state.rerender),
                        rx.text(c.total_comments),
                        rx.text(c.total_comments),
                    ),
                    grid_template_columns="1fr 1fr 1fr 1fr 8fr 1fr 2fr 1fr 1fr 1fr 1fr 2fr 1fr 1fr",
                    py=1,
                    px=1,
                    gap=1,
                    **control_panel_text_style,
            ),
            border="1px solid #ededed",
            border_radius="10px",
            padding=2,
            gap=4,
            mt=2
        )

def reckoning(state, r: Reckoning):
    return rx.match(
        (r.type),
        (ReckoningTypes.concept, render_concept(state, r)),
        (ReckoningTypes.draft, render_concept(state, r)),
        (ReckoningTypes.support, render_comment(state, r)),
        (ReckoningTypes.detract, render_comment(state, r)),
        (ReckoningTypes.point_of_order, render_comment(state, r)),
        (ReckoningTypes.up_vote, render_vote(state, r)),
        (ReckoningTypes.down_vote, render_vote(state, r)),
    )

def page(state, *args, **kwargs):
    return container(
        *args,
        rx.grid(
            rx.box(
                rx.foreach(
                    state.reckonings,
                    lambda r: reckoning(state, r),
                ),
                h="100%",
            ),
            grid_template_columns="1fr",
            h="100vh",
            gap=4,
        ),
        comment_modal(on_close=state.close_modal, on_close_complete=state.close_complete_modal),
        concept_modal(on_close=state.close_modal, on_close_complete=state.close_complete_modal),
        feedback_modal(reckoning_feedback_options, on_close=FeedbackModalState.close),
        max_width="960px",
        **kwargs,
    )


@rx.page(route="/your_reckonings", on_load=YourReckoningsPageState.on_load, **page_params)
def your_reckonings():
    """The your reckonings page."""
    return page(YourReckoningsPageState, navbar(search(YourReckoningsPageState)))

@rx.page(route="/trending_concepts", on_load=TrendingConceptsPageState.on_load, **page_params)
def trending_concepts():
    """The trending concepts page."""
    return page(TrendingConceptsPageState, navbar(search(TrendingConceptsPageState)))

@rx.page(route="/new_concepts", on_load=NewConceptsPageState.on_load, **page_params)
def new_concepts():
    """The new concepts page."""
    return page(NewConceptsPageState, navbar(search(NewConceptsPageState)))

@rx.page(route="/your_drafts", on_load=YourDraftsPageState.on_load, **page_params)
def your_drafts():
    """The your drafts page."""
    return page(YourDraftsPageState, navbar(search(YourDraftsPageState)))

@rx.page(route="/compare/[rid]", on_load=ComparePageState.on_load, **page_params)
def compare():
    """The compare page."""
    return page(ComparePageState, navbar(search(ComparePageState)))

@rx.page(route="/concept/[rid]", on_load=ConceptPageState.on_load, **page_params)
def concept():
    """The concept page."""
    return page(ConceptPageState, navbar())

@rx.page(route="/comments/[rid]", on_load=CommentsPageState.on_load, **page_params)
def comments():
    """The comments page."""
    return page(CommentsPageState, navbar(parent_reckoning(CommentsPageState)))