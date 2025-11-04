"""The your reckonings page."""

import reflex as rx
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import select, delete, func
from sqlalchemy.orm import aliased
from sqlalchemy import and_ as _and, or_ as _or
from rhiz.state.base import AppState, Reckoning, ReckoningTypes
from rhiz.styles import (
    vote_count_and_timestamp_style,
    comment_badge_style,
    popover_button_style,
    input_style,
    page_params,
    interior_grid_style,
    read_only_text_style,
    reckoning_grid_style,
)
from ..components import container, navbar, editor
from rhiz.components.buttons import (
    sort_by_upvotes_button,
    sort_by_support_button,
    your_drafts_button,
    disabled_delete_button,
    disabled_edit_button,
    disabled_feedback_button,
    more_button,
    upvote_concept_button,
    downvote_concept_button,
    feedback_button,
    view_comments_button,
    compare_concepts_button,
    delete_button,
    support_comment_button,
    detract_from_comment_button,
    poo_comment_button,
    feedback_button,
    no_upvote_concept_button,
    no_downvote_concept_button,
    edit_button,
    view_concept_button,
    view_parent_button,
)
from rhiz.components.feedback_dialog import (
    feedback_dialog,
    FeedbackDialogState,
    reckoning_feedback_options,
)
from rhiz.components.concept_dialog import concept_dialog, ConceptDialogState
from rhiz.components.comment_dialog import comment_dialog, CommentDialogState
from rhiz.utils.db import find_similar_texts_with_join


def support_nudge_wrapper(button, on_support):
    """Wrap the support button with guidance for newly submitted concepts."""

    tooltip_style = {
        "background": "white",
        "border": "1px solid rgba(15, 23, 42, 0.1)",
        "box_shadow": "0px 12px 32px rgba(15, 23, 42, 0.18)",
        "border_radius": "12px",
        "padding": "16px",
        "width": "260px",
        "z_index": "50",
    }

    arrow_style = {
        "position": "absolute",
        "width": "14px",
        "height": "14px",
        "background": "white",
        "border_left": "1px solid rgba(15, 23, 42, 0.1)",
        "border_top": "1px solid rgba(15, 23, 42, 0.1)",
        "transform": "rotate(45deg)",
        "left": "calc(50% - 7px)",
        "top": "-7px",
        "box_shadow": "0px -10px 24px rgba(15, 23, 42, 0.12)",
    }

    return rx.box(
        button,
        rx.box(
            rx.vstack(
                rx.text(
                    "Support your concept to share it publicly.",
                    weight="medium",
                ),
                rx.text(
                    "Concepts stay private until you support them yourself or someone else does.",
                    size="2",
                    style={"color": "#475569"},
                ),
                rx.hstack(
                    rx.button(
                        "Support it now",
                        size="1",
                        variant="solid",
                        on_click=on_support,
                    ),
                    rx.button(
                        "Maybe later",
                        size="1",
                        variant="soft",
                        on_click=AppState.dismiss_support_nudge,
                        color_scheme="gray",
                    ),
                    spacing="2",
                ),
                align="start",
                spacing="3",
            ),
            rx.box(**arrow_style),
            position="absolute",
            top="calc(100% + 16px)",
            left="50%",
            **tooltip_style,
        ),
        position="relative",
        display="inline-flex",
    )


class ReckoningsPageState(AppState):
    reckonings: list[Reckoning] = []
    search: str = ""
    page_type: int = 0
    rerender: bool = False

    def new_comment(self, subject, type, pid):
        result = self.check_login()
        if result:
            return result
        if type == ReckoningTypes.support:
            self.dismiss_support_nudge()
        yield CommentDialogState.new_comment(subject, type, pid)
        yield CommentDialogState.visible()
        yield self.save_scroll_position()

    def edit_comment(self, pid, type, cid, content):
        yield CommentDialogState.edit_comment(pid, type, cid, content)
        yield CommentDialogState.visible()

    def edit_concept(self, cid):
        yield ConceptDialogState.set_concept(cid)
        yield ConceptDialogState.visible()

    def provide_feedback_on_reckoning(self, rid):
        result = self.check_login()
        if result:
            return result
        yield FeedbackDialogState.set_reckoning(rid)
        yield FeedbackDialogState.visible()

    def close_modal(self):
        pass

    def compare_concepts(self, cid):
        return rx.redirect(f"/compare/{cid}")

    def view_comments(self, cid):
        return rx.redirect(f"/comments/{cid}")

    def trigger_rerender(self):
        self.rerender = not (self.rerender)

    def vote_on_concept(self, cid, type):
        result = self.check_login()
        if result:
            return result
        with rx.session() as session:
            session.expire_on_commit = False
            concept = session.exec(select(Reckoning).where(Reckoning.id == cid)).first()
            vote = session.exec(
                select(Reckoning).where(
                    _and(
                        Reckoning.parent_reckoning_id == cid,
                        Reckoning.user_id == self.user.id,
                        _or(
                            Reckoning.type == ReckoningTypes.up_vote,
                            Reckoning.type == ReckoningTypes.down_vote,
                        ),
                    )
                )
            ).first()

            if vote:
                if vote.type == type:  # Check if no other votes have been made
                    session.delete(vote)

                    # Check if there are other votes from different users
                    other_votes_count = session.exec(
                        select(func.count(Reckoning.id)).where(
                            _and(
                                Reckoning.parent_reckoning_id == cid,
                                Reckoning.user_id
                                != self.user.id,  # Exclude current user's votes
                                _or(
                                    Reckoning.type == ReckoningTypes.up_vote,
                                    Reckoning.type == ReckoningTypes.down_vote,
                                ),
                            )
                        )
                    ).first()  # Assuming the count result is the first element

                    if other_votes_count == 0:
                        concept.type = ReckoningTypes.draft
                else:
                    vote.type = type
                session.commit()
            else:
                if concept.user_id == self.user.id:
                    concept.type = ReckoningTypes.concept
                comment = Reckoning(
                    content="n/a",
                    parent_reckoning_id=cid,
                    type=type,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    user_id=self.user.id,
                )
                session.add(comment)
                session.commit()

            if type == ReckoningTypes.up_vote:
                self.dismiss_support_nudge()

            yield self.save_scroll_position()
            current_path = self.router.url.path or "/"
            return rx.redirect(current_path)  # return rx.redirect(f"/comments/{cid}")


class YourDraftsPageState(ReckoningsPageState):

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
        self.page_type = 1
        result = self.check_login()
        if result:
            return result
        self.get_reckonings()
        yield self.scroll_to_saved_position()

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            # Start with the base query, including the ordering and common conditions
            query = (
                select(Reckoning)
                .order_by(Reckoning.created_at.desc())
                .where(
                    _and(
                        Reckoning.type == ReckoningTypes.draft,
                        Reckoning.user_id == self.user.id,
                    )
                )
            )

            # If self.search is provided, add an additional condition to the query
            if self.search:
                query = query.where(
                    func.lower(Reckoning.content).contains(self.search.lower())
                )

            # Execute the query to get the results, ensuring uniqueness
            self.reckonings = session.exec(query).unique().all()

            for r in self.reckonings:
                r.compute_tallies(self.user.id)


class NewConceptsPageState(ReckoningsPageState):

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
        self.page_type = 2
        result = self.check_login()
        if result:
            return result
        self.get_reckonings()
        yield self.scroll_to_saved_position()

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            # Start with the base query, applying ordering and a condition that filters by type
            query = (
                select(Reckoning)
                .order_by(Reckoning.created_at.desc())
                .where(
                    _or(
                        Reckoning.type == ReckoningTypes.concept,
                        Reckoning.type == ReckoningTypes.draft,
                    )
                )
            )

            # If self.search is provided, add an additional condition to the query
            if self.search:
                query = query.where(
                    func.lower(Reckoning.content).contains(self.search.lower())
                )

            # Execute the query to get the results
            self.reckonings = session.exec(query).all()

            for r in self.reckonings:
                r.compute_tallies(self.user.id)


class TrendingConceptsByUpvotesPageState(ReckoningsPageState):

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
        self.page_type = 3
        result = self.check_login()
        if result:
            return result
        self.get_reckonings()
        yield self.scroll_to_saved_position()

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            # Create an alias for child reckonings to differentiate from parent reckonings in the self-join
            ChildReckoning = aliased(Reckoning)

            # Subquery to count the number of "up_vote" type child reckonings for each parent
            up_vote_count_subquery = (
                select(
                    ChildReckoning.parent_reckoning_id,
                    func.count(ChildReckoning.id).label("up_vote_count"),
                )
                .where(ChildReckoning.type == ReckoningTypes.up_vote)
                .group_by(ChildReckoning.parent_reckoning_id)
                .subquery()
            )

            # Start building the base query for selecting reckonings and the count of their up_votes
            # Adjust the where condition as needed to filter by specific reckoning types
            query = (
                select(Reckoning, up_vote_count_subquery.c.up_vote_count)
                .outerjoin(
                    up_vote_count_subquery,
                    Reckoning.id == up_vote_count_subquery.c.parent_reckoning_id,
                )
                .where(Reckoning.type == ReckoningTypes.concept)
            )

            # Conditionally add the search filter if `self.search` is provided
            if self.search:
                query = query.where(
                    func.lower(Reckoning.content).contains(self.search.lower())
                )

            # Apply ordering by up_vote count and then by created_at timestamp
            query = query.order_by(
                up_vote_count_subquery.c.up_vote_count.desc(),
                Reckoning.created_at.desc(),
            )

            # Execute the query and fetch all results
            results = session.exec(query).unique().all()

            # Extract Reckoning objects from the results
            self.reckonings = [result[0] for result in results]

            for r in self.reckonings:
                r.compute_tallies(self.user.id)


class TrendingConceptsBySupportPageState(ReckoningsPageState):

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
        self.page_type = 8
        result = self.check_login()
        if result:
            return result
        self.get_reckonings()
        yield self.scroll_to_saved_position()

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            # Create an alias for child reckonings to differentiate from parent reckonings in the self-join
            ChildReckoning = aliased(Reckoning)

            # Subquery to count the number of supportive comments (supports) type child reckonings for each parent
            supportive_comments_count_subquery = (
                select(
                    ChildReckoning.parent_reckoning_id,
                    func.count(ChildReckoning.id).label("supportive_comments_count"),
                )
                .where(
                    ChildReckoning.type == ReckoningTypes.support
                )  # Adjust this condition as needed
                .group_by(ChildReckoning.parent_reckoning_id)
                .subquery()
            )

            # Start building the base query for selecting reckonings and the count of their supportive comments
            query = (
                select(
                    Reckoning,
                    supportive_comments_count_subquery.c.supportive_comments_count,
                )
                .outerjoin(
                    supportive_comments_count_subquery,
                    Reckoning.id
                    == supportive_comments_count_subquery.c.parent_reckoning_id,
                )
                .where(Reckoning.type == ReckoningTypes.concept)
            )

            # Conditionally add the search filter if `self.search` is provided
            if self.search:
                query = query.where(
                    func.lower(Reckoning.content).contains(self.search.lower())
                )

            # Apply ordering by supportive comments count and then by created_at timestamp
            query = query.order_by(
                supportive_comments_count_subquery.c.supportive_comments_count.asc(),
                Reckoning.created_at.asc(),
            )

            # Execute the query and fetch all results
            results = session.exec(query).unique().all()

            # Extract Reckoning objects from the results
            self.reckonings = [result[0] for result in results]

            for r in self.reckonings:
                r.compute_tallies(self.user.id)


class YourConceptsPageState(ReckoningsPageState):

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
        self.page_type = 4
        result = self.check_login()
        if result:
            return result
        self.get_reckonings()
        yield self.scroll_to_saved_position()

    """The state for the your reckonings page."""

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        with rx.session() as session:
            # Start with the base query
            query = select(Reckoning).order_by(Reckoning.created_at.desc())

            # Define common conditions
            common_conditions = [
                Reckoning.type != ReckoningTypes.concept,
                Reckoning.user_id == self.user.id,
                Reckoning.type != ReckoningTypes.draft,
            ]

            # If self.search is provided, add the search condition
            if self.search:
                common_conditions.append(
                    func.lower(Reckoning.content).contains(self.search.lower())
                )

            # Apply conditions to the query
            query = query.where(_and(*common_conditions))

            # Execute the query
            self.reckonings = session.exec(query).unique().all()

            for r in self.reckonings:
                r.cache_parent_details(self.user.id)
                r.compute_tallies(self.user.id)


class ComparePageState(ReckoningsPageState):

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
        self.page_type = 5
        result = self.check_login()
        if result:
            return result
        self.get_reckonings()
        yield self.scroll_to_saved_position()

    @rx.var
    def reckoning_id(self) -> str:
        return self.get_path_param("rid", "no rid")

    def get_reckonings(self):
        """Get reckonings of type concept for this user from the database."""
        primary_keys = []
        with rx.session() as session:
            session.expire_on_commit = False
            try:
                rid = int(self.reckoning_id)
            except ValueError:
                self.dismiss_support_nudge()
                self.reckonings = []
                return

            concept = session.exec(
                select(Reckoning).where(Reckoning.id == rid)
            ).one_or_none()

            if concept is None:
                self.dismiss_support_nudge()
                self.reckonings = []
                return

            if concept.user_id != self.user.id:
                self.dismiss_support_nudge()
            else:
                self.show_support_nudge = (
                    self.support_nudge_concept_id == concept.id
                )
            primary_keys, results = find_similar_texts_with_join(concept.id, 0.75, 10)

            # Construct the base query with the condition that applies in both cases
            query = select(Reckoning).where(Reckoning.id.in_(primary_keys))

            # Conditionally add the search filter if `self.search` is provided
            if self.search:
                query = query.where(
                    func.lower(Reckoning.content).contains(self.search.lower())
                )

            # Execute the query
            self.reckonings = session.exec(query).all()

            # Creating a mapping of ID to reckoning for fast lookup
            id_to_reckoning = {reckoning.id: reckoning for reckoning in self.reckonings}

            # Ordering the reckonings in Python according to the order of IDs in primary_keys
            ordered_reckonings = [
                id_to_reckoning[id] for id in primary_keys if id in id_to_reckoning
            ]

            # Now ordered_reckonings contains your objects in the order of primary_keys
            self.reckonings = ordered_reckonings

            results_dict = dict(results)

            for r in self.reckonings:
                r.similarity = round(
                    ((results_dict[r.id] - 1) * -1), 2
                )  # reverse scale from 0 - infinity to 1 - 0
                r.compute_tallies(self.user.id)


class ConceptPageState(ReckoningsPageState):
    """The state for the comment page."""

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
        self.page_type = 6
        result = self.check_login()
        if result:
            return result
        self.get_reckonings()

    def get_reckonings(self):
        """Get reckoning with rid of cid from the database."""
        with rx.session() as session:
            self.reckonings = [
                session.exec(
                    select(Reckoning).where(Reckoning.id == self.concept_id)
                ).first()
            ]
            for r in self.reckonings:
                r.compute_tallies(self.user.id)

    @rx.var
    def concept_id(self) -> str:
        return self.get_path_param("rid", "no rid")


class CommentsPageState(ReckoningsPageState):
    """The state for the comments page."""

    parent: Optional[Reckoning] = None

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
        # result = self.check_login()
        # if result:
        #     return result
        self.get_reckonings()
        yield self.scroll_to_saved_position()

    def fetch_children(
        self, session, parent_id: int, depth: int = 0, max_depth: int = -1
    ):
        """Recursive function to fetch children of a reckoning, setting depth accordingly, up to max_depth."""
        if max_depth == 0:
            return  # Stop recursion if max depth is reached

        query = (
            select(Reckoning)
            .where(Reckoning.parent_reckoning_id == parent_id)
            .order_by(Reckoning.created_at.asc())
        )

        # Apply common conditions
        common_conditions = (
            Reckoning.content
            != "This reckoning did not include a comment. Feel free to add one.",
            Reckoning.type.in_(
                [
                    ReckoningTypes.support,
                    ReckoningTypes.detract,
                    ReckoningTypes.point_of_order,
                ]
            ),
        )

        if self.search:
            search_condition = func.lower(Reckoning.content).contains(
                func.lower(self.search)
            )
            conditions = (*common_conditions, search_condition)
        else:
            conditions = common_conditions

        query = query.where(*conditions)
        children = session.exec(query).all()

        for child in children:
            child.depth = (
                "4px" if depth == 0 else (str(depth * 20) + "px")
            )  # Set the depth for each child
            child.compute_tallies(self.user.id if self.user else None)
            self.reckonings.append(child)
            if max_depth == -1 or depth < max_depth - 1:
                self.fetch_children(session, child.id, depth + 1, max_depth)

    def get_reckonings(self):
        """Get reckonings for this parent reckoning from the database, recursively fetching children."""
        self.reckonings = []
        with rx.session() as session:
            self.parent = session.exec(
                select(Reckoning).where(Reckoning.id == self.reckoning_id)
            ).first()
            if self.parent is not None:
                self.parent.compute_tallies(self.user.id if self.user else None)

                # Recursively fetch children with conditions applied
                max_depth = 3
                self.fetch_children(session, self.reckoning_id, 0, max_depth)

            # return self.reckonings

    # def get_reckonings(self):
    #     """Get comments for this reckoning from the database."""
    #     with rx.session() as session:
    #         self.parent = session.exec(select(Reckoning).where(Reckoning.id == self.reckoning_id)).first()
    #         self.parent.compute_tallies(self.user.id)

    #         # Start building the base query
    #         query = select(Reckoning).order_by(Reckoning.created_at.asc())

    #         # Common conditions that are always applied
    #         common_conditions = (
    #             Reckoning.content != "This reckoning did not include a comment. Feel free to add one.",
    #             Reckoning.parent_reckoning_id == self.reckoning_id,
    #             _or(
    #                 Reckoning.type == ReckoningTypes.support,
    #                 Reckoning.type == ReckoningTypes.detract,
    #                 Reckoning.type == ReckoningTypes.point_of_order
    #             )
    #         )

    #         if self.search:
    #             # Add the search condition only if self.search is not empty
    #             search_condition = func.lower(Reckoning.content).contains(self.search.lower())
    #             conditions = _and(search_condition, *common_conditions)
    #         else:
    #             conditions = _and(*common_conditions)

    #         # Finalize the query with conditions
    #         query = query.where(conditions)

    #         # Execute the query
    #         self.reckonings = session.exec(query).unique().all()

    #         for r in self.reckonings:
    #             r.compute_tallies(self.user.id)

    @rx.var
    def reckoning_id(self) -> str:
        return self.get_path_param("rid", "no rid")


def parent_reckoning(state):
    """The parent reckoning component."""
    if state.parent is None:
        return rx.box()

    should_show_nudge = (
        state.show_support_nudge
        & (state.support_nudge_concept_id == state.parent.id)
    )
    support_action = state.vote_on_concept(state.parent.id, ReckoningTypes.up_vote)
    support_button = no_upvote_concept_button(on_click=support_action)
    support_button_with_nudge = rx.cond(
        should_show_nudge,
        support_nudge_wrapper(support_button, support_action),
        support_button,
    )

    return rx.grid(
        rx.grid(
            rx.match(
                state.parent.type,
                (
                    ReckoningTypes.support,
                    rx.image(src="/support_comment.svg", **comment_badge_style),
                ),
                (
                    ReckoningTypes.detract,
                    rx.image(src="/detract_from_comment.svg", **comment_badge_style),
                ),
                (
                    ReckoningTypes.point_of_order,
                    rx.image(src="/poo_comment.svg", **comment_badge_style),
                ),
            ),
            editor(
                key=state.parent.id,
                default_value=state.parent.content,
                hide_toolbar=True,
                disable=True,
            ),
            rx.grid(
                rx.cond(
                    (state.parent.user_id != state.user.id),
                    feedback_button(
                        on_click=state.provide_feedback_on_reckoning(state.parent.id),
                    ),
                    disabled_feedback_button(),
                ),
                rx.cond(
                    state.parent.parent_reckoning_id,
                    view_parent_button(
                        on_click=rx.redirect(
                            f"/comments/{state.parent.parent_reckoning_id}"
                        ),
                    ),
                    compare_concepts_button(
                        on_click=rx.redirect(f"/compare/{state.parent.id}"),
                    ),
                ),
                rx.spacer(),
                rx.cond(
                    (state.parent.type == 0),
                    rx.fragment(
                        rx.cond(
                            (
                                state.parent.user_vote_history == ReckoningTypes.no_vote
                            ),
                            rx.fragment(
                                support_button_with_nudge,
                                rx.text(state.parent.up_votes),
                                no_downvote_concept_button(
                                    on_click=state.vote_on_concept(
                                        state.parent.id, ReckoningTypes.down_vote
                                    )
                                ),
                                rx.text(state.parent.down_votes),
                            ),
                            None,
                        ),
                        rx.cond(
                            (
                                state.parent.user_vote_history == ReckoningTypes.up_vote
                            ),
                            rx.fragment(
                                upvote_concept_button(on_click=support_action),
                                rx.text(state.parent.up_votes),
                                no_downvote_concept_button(
                                    on_click=state.vote_on_concept(
                                        state.parent.id, ReckoningTypes.down_vote
                                    )
                                ),
                                rx.text(state.parent.down_votes),
                            ),
                            None,
                        ),
                        rx.cond(
                            (
                                state.parent.user_vote_history
                                == ReckoningTypes.down_vote
                            ),
                            rx.fragment(
                                no_upvote_concept_button(on_click=support_action),
                                rx.text(state.parent.up_votes),
                                downvote_concept_button(
                                    on_click=state.vote_on_concept(
                                        state.parent.id, ReckoningTypes.down_vote
                                    )
                                ),
                                rx.text(state.parent.down_votes),
                            ),
                            None,
                        ),
                    ),
                    rx.fragment(
                        rx.spacer(),
                        rx.spacer(),
                        rx.spacer(),
                        rx.spacer(),
                    ),
                ),
                rx.spacer(),
                support_comment_button(
                    on_click=state.new_comment(
                        state.parent.content,
                        ReckoningTypes.support,
                        state.reckoning_id,
                    )
                ),
                rx.text(state.parent.supports),
                poo_comment_button(
                    on_click=state.new_comment(
                        state.parent.content,
                        ReckoningTypes.point_of_order,
                        state.reckoning_id,
                    )
                ),
                rx.text(state.parent.points_of_order),
                detract_from_comment_button(
                    on_click=state.new_comment(
                        state.parent.content, ReckoningTypes.detract, state.reckoning_id
                    )
                ),
                rx.text(state.parent.detracts),
                grid_template_columns="1fr 1fr 11fr 1fr 0.5fr 1fr 0.5fr 0.5fr 1fr 0.5fr 1fr 0.5fr 1fr 0.5fr",
                **interior_grid_style,
            ),
            **reckoning_grid_style,
            position="relative",
        ),
        # rx.input(on_change=state.set_search, placeholder="Search comments", **input_style),
        **interior_grid_style,
    )


def search_navbar(state):
    """The your concepts component of the navbar."""
    return rx.grid(
        rx.input(
            on_change=state.set_search, placeholder="Search concepts", **input_style
        ),
        **interior_grid_style,
        margin="8px 0 0 0",
    )


def your_concepts_navbar(state):
    """The your concepts component of the navbar."""
    return rx.grid(
        rx.input(
            on_change=state.set_search, placeholder="Search concepts", **input_style
        ),
        your_drafts_button(),
        **interior_grid_style,
        grid_template_columns="22fr 1fr",
        margin="8px 0 0 0",
    )


def trending_concepts_navbar(state):
    """The trending component of the navbar."""
    return rx.grid(
        rx.spacer(),
        sort_by_support_button(),
        sort_by_upvotes_button(),
        **interior_grid_style,
        grid_template_columns="21fr 1fr 1fr",
        margin="8px 0 0 0",
    )


def render_comment(state, c: Reckoning):
    """Display for an individual comment in the feed."""
    support_button_component = support_comment_button(
        on_click=state.new_comment(c.content, ReckoningTypes.support, c.id)
    )

    return rx.grid(
        rx.grid(
            rx.cond(
                (state.page_type == 4),
                rx.cond(
                    (c.parent_type == ReckoningTypes.concept),
                    rx.fragment(
                        rx.markdown(
                            c.parent_content,
                            class_name="prose",
                            max_width="100%",
                            **read_only_text_style,
                        ),
                        rx.grid(
                            view_parent_button(
                                on_click=rx.redirect(f"/comments/{c.parent_id}"),
                            ),
                            rx.spacer(),
                            rx.cond(
                                (
                                    c.parent_user_vote_history == ReckoningTypes.no_vote
                                ),  # & (c.user_id != state.user.id),
                                rx.fragment(
                                    no_upvote_concept_button(
                                        on_click=state.vote_on_concept(
                                            c.parent_id, ReckoningTypes.up_vote
                                        )
                                    ),
                                    rx.text(c.parent_up_votes),
                                    no_downvote_concept_button(
                                        on_click=state.vote_on_concept(
                                            c.parent_id, ReckoningTypes.down_vote
                                        )
                                    ),
                                    rx.text(c.parent_down_votes),
                                ),
                                None,
                            ),
                            rx.cond(
                                (
                                    c.parent_user_vote_history == ReckoningTypes.up_vote
                                ),  # | (c.user_id == state.user.id),
                                rx.fragment(
                                    upvote_concept_button(
                                        on_click=state.vote_on_concept(
                                            c.parent_id, ReckoningTypes.up_vote
                                        )
                                    ),
                                    rx.text(c.parent_up_votes),
                                    no_downvote_concept_button(
                                        on_click=state.vote_on_concept(
                                            c.parent_id, ReckoningTypes.down_vote
                                        )
                                    ),
                                    rx.text(c.parent_down_votes),
                                ),
                                None,
                            ),
                            rx.cond(
                                (
                                    c.parent_user_vote_history
                                    == ReckoningTypes.down_vote
                                ),
                                rx.fragment(
                                    no_upvote_concept_button(
                                        on_click=state.vote_on_concept(
                                            c.parent_id, ReckoningTypes.up_vote
                                        )
                                    ),
                                    rx.text(c.parent_up_votes),
                                    downvote_concept_button(
                                        on_click=state.vote_on_concept(
                                            c.parent_id, ReckoningTypes.down_vote
                                        )
                                    ),
                                    rx.text(c.parent_down_votes),
                                ),
                                None,
                            ),
                            grid_template_columns="1fr 18fr 1fr 1fr 1fr 1fr",
                            **interior_grid_style,
                        ),
                    ),
                    rx.grid(
                        rx.box(
                            rx.flex(
                                rx.match(
                                    c.parent_type,
                                    (
                                        ReckoningTypes.support,
                                        rx.image(
                                            src="/support_comment.svg",
                                            width="24px",
                                            height="24px",
                                        ),
                                    ),
                                    (
                                        ReckoningTypes.detract,
                                        rx.image(
                                            src="/detract_from_comment.svg",
                                            width="24px",
                                            height="24px",
                                        ),
                                    ),
                                    (
                                        ReckoningTypes.point_of_order,
                                        rx.image(
                                            src="/poo_comment.svg",
                                            width="24px",
                                            height="24px",
                                        ),
                                    ),
                                ),
                                **comment_badge_style,
                            ),
                            rx.markdown(
                                c.parent_content,
                                class_name="prose",
                                max_width="100%",
                                **read_only_text_style,
                            ),
                            rx.flex(
                                rx.text(c.parent_elapsed_time, size="1", flex_grow="1"),
                                **vote_count_and_timestamp_style,
                                direction="row",
                                align="end",
                            ),
                            position="relative",
                        ),
                        rx.grid(
                            view_parent_button(
                                on_click=rx.redirect(
                                    f"/comments/{c.parent_reckoning_id}"
                                ),
                            ),
                            rx.spacer(),
                            grid_template_columns="1fr 22fr",
                            **interior_grid_style,
                        ),
                        **interior_grid_style,
                    ),
                ),
                None,
            ),
            rx.grid(
                rx.box(
                    rx.flex(
                        rx.match(
                            c.type,
                            (
                                ReckoningTypes.support,
                                rx.image(
                                    src="/support_comment.svg",
                                    width="24px",
                                    height="24px",
                                ),
                            ),
                            (
                                ReckoningTypes.detract,
                                rx.image(
                                    src="/detract_from_comment.svg",
                                    width="24px",
                                    height="24px",
                                ),
                            ),
                            (
                                ReckoningTypes.point_of_order,
                                rx.image(
                                    src="/poo_comment.svg", width="24px", height="24px"
                                ),
                            ),
                        ),
                        **comment_badge_style,
                    ),
                    rx.markdown(
                        c.content,
                        class_name="prose",
                        max_width="100%",
                        **read_only_text_style,
                    ),
                    rx.flex(
                        rx.text(c.elapsed_time, size="1", flex_grow="1"),
                        **vote_count_and_timestamp_style,
                        direction="row",
                        align="end",
                    ),
                    position="relative",
                ),
                rx.grid(
                    rx.popover.root(
                        rx.popover.trigger(
                            more_button(),
                        ),
                        rx.popover.content(
                            rx.flex(
                                rx.cond(
                                    (c.user_id != state.user.id),
                                    feedback_button(
                                        **popover_button_style,
                                        on_click=state.provide_feedback_on_reckoning(
                                            c.id
                                        ),
                                    ),
                                    disabled_feedback_button(**popover_button_style),
                                ),
                                rx.cond(
                                    (
                                        (state.user.role > 0)
                                        | (
                                            (c.user_id == state.user.id)
                                            & (c.supports == 0)
                                            & (c.detracts == 0)
                                            & (c.points_of_order == 0)
                                        )
                                    ),
                                    edit_button(
                                        **popover_button_style,
                                        on_click=state.edit_comment(
                                            c.parent_reckoning_id,
                                            c.type,
                                            c.id,
                                            c.content,
                                        ),
                                    ),
                                    disabled_edit_button(**popover_button_style),
                                ),
                                rx.cond(
                                    (
                                        (state.user.role > 0)
                                        | (
                                            (c.user_id == state.user.id)
                                            & (c.supports == 0)
                                            & (c.detracts == 0)
                                            & (c.points_of_order == 0)
                                        )
                                    ),
                                    delete_button(
                                        **popover_button_style,
                                        on_click=state.delete_reckoning(c.id),
                                    ),
                                    disabled_delete_button(**popover_button_style),
                                ),
                                direction="row",
                                spacing="3",
                                size="1",
                            ),
                            side="top",
                            align="center",
                        ),
                    ),
                    rx.cond(
                        ((c.total_comments > 0) & (c.depth == "40px")),
                        view_comments_button(
                            on_click=state.view_comments(c.id),
                        ),
                        rx.spacer(),
                    ),
                    rx.spacer(),
                    support_button_component,
                    rx.text(c.supports),
                    poo_comment_button(
                        on_click=state.new_comment(
                            c.content, ReckoningTypes.point_of_order, c.id
                        )
                    ),
                    rx.text(c.points_of_order),
                    detract_from_comment_button(
                        on_click=state.new_comment(
                            c.content, ReckoningTypes.detract, c.id
                        )
                    ),
                    rx.text(c.detracts),
                    grid_template_columns="1fr 1fr 14fr 1fr 1fr 1fr 1fr 1fr 1fr",
                    **interior_grid_style,
                ),
                **interior_grid_style,
                position="relative",
            ),
            **interior_grid_style,
        ),
        **reckoning_grid_style,
        margin_left=c.depth,
    )


def render_concept_template(state, c: Reckoning, item_attributes: dict):
    """Display for an individual item (vote or concept) in the feed, dynamically adapting based on attributes."""
    item_id = getattr(c, item_attributes["id"])
    content = getattr(c, item_attributes["content"])
    vote_history = getattr(c, item_attributes["vote_history"])
    up_votes = getattr(c, item_attributes["up_votes"])
    down_votes = getattr(c, item_attributes["down_votes"])
    total_comments = getattr(c, item_attributes["total_comments"])
    elapsed_time = getattr(c, item_attributes["elapsed_time"])

    support_action = state.vote_on_concept(item_id, ReckoningTypes.up_vote)
    support_button = no_upvote_concept_button(on_click=support_action)

    should_show_nudge = (
        state.show_support_nudge
        & (state.support_nudge_concept_id == item_id)
    )

    return rx.grid(
        rx.box(
            rx.markdown(
                content,
                class_name="prose",
                max_width="100%",
                **read_only_text_style,
            ),
            rx.flex(
                rx.text(elapsed_time, size="1", flex_grow="1"),
                **vote_count_and_timestamp_style,
                direction="row",
                align="end",
            ),
            position="relative",
        ),
        rx.grid(
            rx.popover.root(
                rx.popover.trigger(
                    more_button(),
                ),
                rx.popover.content(
                    rx.flex(
                        rx.cond(
                            (c.user_id != state.user.id),
                            feedback_button(
                                **popover_button_style,
                                on_click=state.provide_feedback_on_reckoning(item_id),
                            ),
                            disabled_feedback_button(**popover_button_style),
                        ),
                        rx.cond(
                            (state.page_type == 1),
                            edit_button(
                                **popover_button_style,
                                on_click=state.edit_concept(item_id),
                            ),
                            disabled_edit_button(**popover_button_style),
                        ),
                        rx.cond(
                            (state.page_type == 1),
                            delete_button(
                                **popover_button_style,
                                on_click=state.delete_reckoning(item_id),
                            ),
                            disabled_delete_button(**popover_button_style),
                        ),
                        direction="row",
                        spacing="3",
                        size="1",
                    ),
                    side="top",
                    align="center",
                ),
            ),
            view_concept_button(
                on_click=state.view_comments(item_id),
            ),
            rx.text(total_comments),
            compare_concepts_button(
                on_click=state.compare_concepts(item_id),
            ),
            rx.spacer(),
            rx.cond(
                (state.page_type == 5),
                rx.text(c.similarity),
                rx.spacer(),
            ),
            rx.spacer(),
            rx.cond(
                (vote_history == ReckoningTypes.no_vote),
                rx.fragment(
                    rx.cond(
                        should_show_nudge,
                        support_nudge_wrapper(
                            support_button,
                            support_action,
                        ),
                        support_button,
                    ),
                    rx.text(up_votes),
                    no_downvote_concept_button(
                        on_click=state.vote_on_concept(
                            item_id, ReckoningTypes.down_vote
                        )
                    ),
                    rx.text(down_votes),
                ),
                None,
            ),
            rx.cond(
                (vote_history == ReckoningTypes.up_vote),
                rx.fragment(
                    upvote_concept_button(on_click=support_action),
                    rx.text(up_votes),
                    no_downvote_concept_button(
                        on_click=state.vote_on_concept(
                            item_id, ReckoningTypes.down_vote
                        )
                    ),
                    rx.text(down_votes),
                ),
                None,
            ),
            rx.cond(
                (vote_history == ReckoningTypes.down_vote),
                rx.fragment(
                    no_upvote_concept_button(on_click=support_action),
                    rx.text(up_votes),
                    downvote_concept_button(
                        on_click=state.vote_on_concept(
                            item_id, ReckoningTypes.down_vote
                        )
                    ),
                    rx.text(down_votes),
                ),
                None,
            ),
            grid_template_columns="1fr 1fr 0.5fr 1fr 2fr 1fr 10fr 1fr 1fr 1fr 1fr",
            **interior_grid_style,
        ),
        **reckoning_grid_style,
    )


attributes_for_vote = {
    "id": "parent_id",
    "content": "parent_content",
    "vote_history": "parent_user_vote_history",
    "up_votes": "parent_up_votes",
    "down_votes": "parent_down_votes",
    "total_comments": "parent_total_comments",
    "elapsed_time": "parent_elapsed_time",
}

attributes_for_concept = {
    "id": "id",
    "content": "content",
    "vote_history": "user_vote_history",
    "up_votes": "up_votes",
    "down_votes": "down_votes",
    "total_comments": "total_comments",
    "elapsed_time": "elapsed_time",
}


def render_concept(state, c: Reckoning):
    return render_concept_template(
        state, c, attributes_for_concept
    )  # To render a concept


def render_vote(state, c: Reckoning):
    return render_concept_template(state, c, attributes_for_vote)  # To render a vote


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
            rx.foreach(
                state.reckonings,
                lambda r: reckoning(state, r),
            ),
            h="100vh",
            gap=4,
        ),
        comment_dialog(),
        concept_dialog(),
        feedback_dialog(options=reckoning_feedback_options),
        **kwargs,
    )


@rx.page(
    route="/your_concepts", on_load=YourConceptsPageState.on_load, **page_params
)
def your_concepts():
    """The your reckonings page."""
    return page(
        YourConceptsPageState, navbar(your_concepts_navbar(YourConceptsPageState))
    )


@rx.page(
    route="/trending_concepts_by_upvotes",
    on_load=TrendingConceptsByUpvotesPageState.on_load,
    **page_params,
)
def trending_concepts_by_upvotes():
    """The trending concepts by upvotes page."""
    return page(
        TrendingConceptsByUpvotesPageState,
        navbar(trending_concepts_navbar(TrendingConceptsByUpvotesPageState)),
    )


@rx.page(
    route="/trending_concepts_by_support",
    on_load=TrendingConceptsBySupportPageState.on_load,
    **page_params,
)
def trending_concepts_by_support():
    """The trending concepts by support page."""
    return page(
        TrendingConceptsBySupportPageState,
        navbar(trending_concepts_navbar(TrendingConceptsBySupportPageState)),
    )


@rx.page(route="/new_concepts", on_load=NewConceptsPageState.on_load, **page_params)
def new_concepts():
    """The new concepts page."""
    return page(NewConceptsPageState, navbar(search_navbar(NewConceptsPageState)))


@rx.page(route="/your_drafts", on_load=YourDraftsPageState.on_load, **page_params)
def your_drafts():
    """The your drafts page."""
    return page(YourDraftsPageState, navbar(search_navbar(YourConceptsPageState)))


@rx.page(route="/compare/[rid]", on_load=ComparePageState.on_load, **page_params)
def compare():
    """The compare page."""
    return page(ComparePageState, navbar())


@rx.page(route="/concept/[rid]", on_load=ConceptPageState.on_load, **page_params)
def concept():
    """The concept page."""
    return page(ConceptPageState, navbar())


@rx.page(route="/comments/[rid]", on_load=CommentsPageState.on_load, **page_params)
def comments():
    """The comments page."""
    return page(CommentsPageState, navbar(parent_reckoning(CommentsPageState)))
