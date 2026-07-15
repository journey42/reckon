"""The your reckonings page."""

import reflex as rx
from rhiz.components.safe_markdown import SafeMarkdown
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import select, delete, func
from sqlalchemy.orm import aliased, noload
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
from ..components import container, navbar
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
    graduate_button,
)
from rhiz.components.feedback_dialog import (
    feedback_dialog,
    FeedbackDialogState,
    reckoning_feedback_options,
)
from rhiz.components.concept_dialog import concept_dialog, ConceptDialogState
from rhiz.components.comment_dialog import comment_dialog, CommentDialogState
from rhiz.components.group_dialog import group_dialog
from rhiz.utils.db import find_similar_texts_with_join
from rhiz.utils.permissions import can_manage_groups
from rhiz.utils.groups import get_group_for_concept
from urllib.parse import quote


def _exclude_private_groups():
    """SQLAlchemy filter: only site-wide, public-group, or graduated concepts.

    Site-wide concepts have group_id IS NULL. Public-group concepts have
    group_id pointing at a Group with is_public=True. Graduated concepts
    have is_graduated=True (they keep their group_id but are also visible
    site-wide). Private group concepts that are not graduated are excluded.
    """
    from rhiz.state.base import Group

    return _or(
        Reckoning.group_id.is_(None),
        Reckoning.group_id.in_(
            select(Group.id).where(Group.is_public == True)  # noqa: E712
        ),
        Reckoning.is_graduated == True,  # noqa: E712
    )


NUDGE_HEADING = "!Your idea has NOT been published yet!"
NUDGE_RELATED_BODY = (
    "Your comment is related to a previous entry. You can choose to\n"
    "A) Upvote your own submission to make it “sticky”, or\n"
    "😎 😎 Lend your vote to the previous entry\n"
    "Nothing is public until you make that choice"
)
NUDGE_FIRST_TOPIC_BODY = (
    "Your comment is the first to touch on this topic. Thank you!\n"
    "Your comment will not be public unless you choose to upvote it, this is part of our "
    "decision format in cases where your topic has come up before"
)
NUDGE_COLLAPSED_SUMMARY = "Your idea stays private until you choose how to support it."


def support_nudge_banner(state):
    """Sticky banner that guides users after they submit a concept."""

    banner_style = {
        "position": "sticky",
        "top": "72px",
        "z_index": "90",
        "margin": "0 auto 16px",
        "width": "min(720px, calc(100% - 32px))",
        "background": "white",
        "border": "1px solid rgba(15, 23, 42, 0.1)",
        "box_shadow": "0px 12px 32px rgba(15, 23, 42, 0.18)",
        "border_radius": "12px",
        "transition": "transform 0.3s ease, opacity 0.3s ease",
    }

    support_action = state.support_nudge_support()

    expanded_content = rx.vstack(
        rx.text(NUDGE_HEADING, weight="medium", size="3"),
        rx.cond(
            getattr(state, "nudge_has_matches", False),
            rx.text(
                NUDGE_RELATED_BODY,
                size="2",
                style={"color": "#475569", "whiteSpace": "pre-line"},
            ),
            rx.text(
                NUDGE_FIRST_TOPIC_BODY,
                size="2",
                style={"color": "#475569", "whiteSpace": "pre-line"},
            ),
        ),
        rx.hstack(
            rx.button(
                "Support it now",
                size="1",
                variant="solid",
                on_click=support_action,
            ),
            rx.button(
                "Maybe later",
                size="1",
                variant="soft",
                color_scheme="gray",
                on_click=AppState.dismiss_support_nudge,
            ),
            rx.button(
                "Hide",
                size="1",
                variant="soft",
                color_scheme="gray",
                on_click=AppState.collapse_support_nudge,
                style={"marginLeft": "auto"},
            ),
            spacing="3",
            align_items="start",
            justify="start",
            style={"flexWrap": "wrap", "rowGap": "8px", "columnGap": "8px"},
        ),
        align="start",
        spacing="3",
    )

    collapsed_content = rx.vstack(
        rx.text(
            NUDGE_COLLAPSED_SUMMARY,
            size="2",
            style={"color": "#475569"},
        ),
        rx.hstack(
            rx.button(
                "Show options",
                size="1",
                variant="solid",
                on_click=AppState.expand_support_nudge,
            ),
            rx.button(
                "Dismiss",
                size="1",
                variant="soft",
                color_scheme="gray",
                on_click=AppState.dismiss_support_nudge,
            ),
            spacing="2",
            style={"flexWrap": "wrap", "rowGap": "8px", "columnGap": "8px"},
        ),
        align="start",
        spacing="2",
    )

    return rx.cond(
        state.show_support_nudge,
        rx.box(
            rx.cond(
                state.support_nudge_collapsed,
                rx.box(collapsed_content, padding="12px"),
                rx.box(expanded_content, padding="16px"),
            ),
            style=banner_style,
        ),
        None,
    )


class ReckoningsPageState(AppState):
    reckonings: list[Reckoning] = []
    search: str = ""
    page_type: int = 0
    rerender: bool = False

    # Infinite-scroll windowing. has_more defaults to False so pages that
    # override get_reckonings (Compare, Concept, Comments) never show the
    # sentinel; the flat-list pages flip it on via get_reckonings below.
    page_size: int = 20
    loaded_count: int = 0
    has_more: bool = False
    is_loading: bool = False

    @rx.var
    def user_can_manage_groups(self) -> bool:
        """Whether the current user may create groups."""
        return can_manage_groups(self.user)

    # NOTE: Reflex dispatches a PUBLIC event handler to the substate that
    # *defines* it, so an inherited public `get_reckonings`/`load_more` would
    # run with `self` bound to this base substate (wrong `_window_query`, wrong
    # `reckonings` node). The shared logic therefore lives in PRIVATE helpers
    # (private methods are plain calls that preserve `self`), and each flat-list
    # subclass defines thin public `get_reckonings`/`load_more` wrappers so the
    # handlers dispatch to the correct substate.

    def _window_query(self, session):
        """Return the SQLAlchemy select for this page (ordering + filters).

        Flat-list subclasses override this. The base raises so misuse is loud.
        """
        raise NotImplementedError

    def _load_window(self, append: bool = False):
        """Load one page_size window at the current offset.

        Tallies for the whole window are computed in a few batched queries via
        ``Reckoning.assign_tallies_batch`` rather than per row. ``noload`` keeps
        the self-referential ``child_reckonings`` relationship from eager-loading
        each concept's entire comment/vote subtree (which it otherwise does,
        one round-trip per row, against the remote DB).
        """
        with rx.session() as session:
            query = (
                self._window_query(session)
                .options(noload(Reckoning.child_reckonings))
                .offset(self.loaded_count)
                .limit(self.page_size)
            )
            rows = session.exec(query).unique().all()
            # Multi-entity selects (Trending) return Row tuples; take the model.
            batch = [r if isinstance(r, Reckoning) else r[0] for r in rows]
            Reckoning.assign_tallies_batch(
                batch, self.user.id if self.user else None, session
            )
            self.reckonings = (self.reckonings + batch) if append else batch
            self.loaded_count += len(batch)
            self.has_more = len(batch) == self.page_size

    def _load_first_window(self):
        """(Re)load the first window. Used by on_load/search/delete/vote paths."""
        self.loaded_count = 0
        self.has_more = True
        self._load_window(append=False)

    def _append_next_window(self):
        """Append the next window; triggered by the infinite-scroll sentinel."""
        if self.is_loading or not self.has_more:
            return
        self.is_loading = True
        try:
            self._load_window(append=True)
        finally:
            self.is_loading = False

    def load_more(self):
        """Default handler so the shared view's `state.load_more` reference
        resolves on pages without infinite scroll (no-op: has_more is False).
        Flat-list subclasses override this to dispatch to their own substate."""
        self._append_next_window()

    def _require_login_redirect(self):
        """Gate write/nav actions on the public comments page.

        Anonymous visitors are sent to signup with a return path; when the
        concept they're on is a group, that path is the /group/<slug> link so
        is_debate_origin() matches and the account auto-enables after email
        verification. Logged-in-but-not-enabled users keep the old /login gate.
        """
        if not self.logged_in:
            target = self.router.url.path or "/"
            parts = [p for p in target.split("/") if p]
            if len(parts) >= 2 and parts[0] == "comments":
                try:
                    cid = int(parts[1])
                except ValueError:
                    cid = None
                if cid is not None:
                    with rx.session() as session:
                        group = get_group_for_concept(session, cid)
                    if group is not None:
                        target = f"/group/{group.slug}"
            return rx.redirect(f"/signup?next={quote(target, safe='/')}")
        if not self.user.enabled:
            return rx.redirect("/login")
        return None

    def new_comment(self, subject, type, pid):
        result = self._require_login_redirect()
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
        result = self._require_login_redirect()
        if result:
            return result
        yield FeedbackDialogState.set_reckoning(rid)
        yield FeedbackDialogState.visible()

    def close_modal(self):
        pass

    @rx.event
    def graduate_concept(self, rid: int):
        """Graduate a concept to the main site. No-op on non-group pages."""
        pass

    def compare_concepts(self, cid):
        result = self._require_login_redirect()
        if result:
            return result
        return rx.redirect(f"/compare/{cid}")

    def view_comments(self, cid):
        return rx.redirect(f"/comments/{cid}")

    def trigger_rerender(self):
        self.rerender = not (self.rerender)

    def vote_on_concept(self, cid, type):
        result = self._require_login_redirect()
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

                    if other_votes_count == 0 and concept.group_id is None:
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
                    group_id=concept.group_id,
                )
                session.add(comment)
                session.commit()

            if type == ReckoningTypes.up_vote:
                self.dismiss_support_nudge()

            # Capture PostHog event for vote cast.
            try:
                from rhiz.rhiz import posthog

                if posthog and self.user:
                    posthog.capture(
                        "vote_cast",
                        distinct_id=f"user-{self.user.id}",
                        properties={
                            "event_type": "vote",
                            "vote_type": (
                                "upvote"
                                if type == ReckoningTypes.up_vote
                                else "downvote"
                            ),
                            "target_reckoning_id": cid,
                        },
                    )
            except Exception:
                pass  # PostHog failures should not block voting.

            yield self.save_scroll_position()
            current_path = self.router.url.path or "/"
            return rx.redirect(current_path)  # return rx.redirect(f"/comments/{cid}")

    def support_nudge_support(self):
        """Trigger an upvote via the nudge banner."""
        if self.support_nudge_concept_id is None:
            return
        yield self.stop_support_nudge_pulse()
        result = yield from self.vote_on_concept(
            self.support_nudge_concept_id, ReckoningTypes.up_vote
        )
        return result


class YourDraftsPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Admins can cascade-delete with children;
        non-admins can only delete if the concept has no children."""
        with rx.session() as session:
            if self.user.role >= 2:
                # Admin: cascade delete with all children
                from sqlalchemy import text
                session.execute(
                    text(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT :rid AS id
                            UNION ALL
                            SELECT r.id FROM reckoning r
                            JOIN descendants d ON r.parent_reckoning_id = d.id
                        )
                        DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                        """
                    ),
                    {"rid": rid},
                )
                session.commit()
            else:
                # Non-admin: only delete if no children
                child_count = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.parent_reckoning_id == rid
                    )
                ).first()
                if child_count and child_count > 0:
                    return rx.window_alert(
                        "This concept has comments or votes and cannot be deleted. "
                        "Remove all comments and votes first."
                    )
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
        self._load_first_window()

    def load_more(self):
        self._append_next_window()

    def _window_query(self, session):
        """Drafts owned by the current user, newest first.

        Drafts include group-scoped drafts (converted when a user supports
        someone else's concept at the decision fork) — these should be
        visible to the user who wrote them regardless of group scope.
        """
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

        return query


class NewConceptsPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Admins can cascade-delete with children;
        non-admins can only delete if the concept has no children."""
        with rx.session() as session:
            if self.user.role >= 2:
                # Admin: cascade delete with all children
                from sqlalchemy import text
                session.execute(
                    text(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT :rid AS id
                            UNION ALL
                            SELECT r.id FROM reckoning r
                            JOIN descendants d ON r.parent_reckoning_id = d.id
                        )
                        DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                        """
                    ),
                    {"rid": rid},
                )
                session.commit()
            else:
                # Non-admin: only delete if no children
                child_count = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.parent_reckoning_id == rid
                    )
                ).first()
                if child_count and child_count > 0:
                    return rx.window_alert(
                        "This concept has comments or votes and cannot be deleted. "
                        "Remove all comments and votes first."
                    )
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
        self._load_first_window()

    def load_more(self):
        self._append_next_window()

    def _window_query(self, session):
        """All concepts and drafts, newest first."""
        query = (
            select(Reckoning)
            .order_by(Reckoning.created_at.desc())
            .where(
                _and(
                    _or(
                        Reckoning.type == ReckoningTypes.concept,
                        Reckoning.type == ReckoningTypes.draft,
                    ),
                    _exclude_private_groups(),
                )
            )
        )

        # If self.search is provided, add an additional condition to the query
        if self.search:
            query = query.where(
                func.lower(Reckoning.content).contains(self.search.lower())
            )

        return query


class TrendingConceptsByUpvotesPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Admins can cascade-delete with children;
        non-admins can only delete if the concept has no children."""
        with rx.session() as session:
            if self.user.role >= 2:
                # Admin: cascade delete with all children
                from sqlalchemy import text
                session.execute(
                    text(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT :rid AS id
                            UNION ALL
                            SELECT r.id FROM reckoning r
                            JOIN descendants d ON r.parent_reckoning_id = d.id
                        )
                        DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                        """
                    ),
                    {"rid": rid},
                )
                session.commit()
            else:
                # Non-admin: only delete if no children
                child_count = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.parent_reckoning_id == rid
                    )
                ).first()
                if child_count and child_count > 0:
                    return rx.window_alert(
                        "This concept has comments or votes and cannot be deleted. "
                        "Remove all comments and votes first."
                    )
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
        self._load_first_window()

    def load_more(self):
        self._append_next_window()

    def _window_query(self, session):
        """Concepts ordered by upvote count (desc), then newest first."""
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
            .where(
                _and(
                    Reckoning.type == ReckoningTypes.concept,
                    _exclude_private_groups(),
                )
            )
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

        return query


class TrendingConceptsBySupportPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Admins can cascade-delete with children;
        non-admins can only delete if the concept has no children."""
        with rx.session() as session:
            if self.user.role >= 2:
                # Admin: cascade delete with all children
                from sqlalchemy import text
                session.execute(
                    text(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT :rid AS id
                            UNION ALL
                            SELECT r.id FROM reckoning r
                            JOIN descendants d ON r.parent_reckoning_id = d.id
                        )
                        DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                        """
                    ),
                    {"rid": rid},
                )
                session.commit()
            else:
                # Non-admin: only delete if no children
                child_count = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.parent_reckoning_id == rid
                    )
                ).first()
                if child_count and child_count > 0:
                    return rx.window_alert(
                        "This concept has comments or votes and cannot be deleted. "
                        "Remove all comments and votes first."
                    )
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
        self._load_first_window()

    def load_more(self):
        self._append_next_window()

    def _window_query(self, session):
        """Concepts ordered by supportive-comment count, then created_at (asc)."""
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
            .where(
                _and(
                    Reckoning.type == ReckoningTypes.concept,
                    _exclude_private_groups(),
                )
            )
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

        return query


class YourConceptsPageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Admins can cascade-delete with children;
        non-admins can only delete if the concept has no children."""
        with rx.session() as session:
            if self.user.role >= 2:
                # Admin: cascade delete with all children
                from sqlalchemy import text
                session.execute(
                    text(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT :rid AS id
                            UNION ALL
                            SELECT r.id FROM reckoning r
                            JOIN descendants d ON r.parent_reckoning_id = d.id
                        )
                        DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                        """
                    ),
                    {"rid": rid},
                )
                session.commit()
            else:
                # Non-admin: only delete if no children
                child_count = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.parent_reckoning_id == rid
                    )
                ).first()
                if child_count and child_count > 0:
                    return rx.window_alert(
                        "This concept has comments or votes and cannot be deleted. "
                        "Remove all comments and votes first."
                    )
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
        self._load_first_window()

    def load_more(self):
        self._append_next_window()

    def _window_query(self, session):
        """The current user's published concepts, newest first."""
        query = (
            select(Reckoning)
            .order_by(Reckoning.created_at.desc())
            .where(
                _and(
                    Reckoning.type == ReckoningTypes.concept,
                    Reckoning.user_id == self.user.id,
                    _exclude_private_groups(),
                )
            )
        )

        # If self.search is provided, add the search condition
        if self.search:
            query = query.where(
                func.lower(Reckoning.content).contains(self.search.lower())
            )

        return query


class ComparePageState(ReckoningsPageState):

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Admins can cascade-delete with children;
        non-admins can only delete if the concept has no children."""
        with rx.session() as session:
            if self.user.role >= 2:
                # Admin: cascade delete with all children
                from sqlalchemy import text
                session.execute(
                    text(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT :rid AS id
                            UNION ALL
                            SELECT r.id FROM reckoning r
                            JOIN descendants d ON r.parent_reckoning_id = d.id
                        )
                        DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                        """
                    ),
                    {"rid": rid},
                )
                session.commit()
            else:
                # Non-admin: only delete if no children
                child_count = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.parent_reckoning_id == rid
                    )
                ).first()
                if child_count and child_count > 0:
                    return rx.window_alert(
                        "This concept has comments or votes and cannot be deleted. "
                        "Remove all comments and votes first."
                    )
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
                self.show_support_nudge = self.support_nudge_concept_id == concept.id
            # Scope similarity search to the same group (or site-wide if not in a group)
            primary_keys, results = find_similar_texts_with_join(
                concept.id, 0.75, 10, group_id=concept.group_id
            )
            similar_ids = [pk for pk in primary_keys if pk != concept.id]
            self.nudge_has_matches = bool(similar_ids)

            # Construct the base query — when comparing a group concept,
            # don't apply _exclude_private_groups() since we're already scoped
            if concept.group_id is not None:
                query = select(Reckoning).where(Reckoning.id.in_(primary_keys))
            else:
                query = select(Reckoning).where(
                    _and(
                        Reckoning.id.in_(primary_keys),
                        _exclude_private_groups(),
                    )
                )

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
                r.compute_tallies(self.user.id, session=session)


class ConceptPageState(ReckoningsPageState):
    """The state for the comment page."""

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Admins can cascade-delete with children;
        non-admins can only delete if the concept has no children."""
        with rx.session() as session:
            if self.user.role >= 2:
                # Admin: cascade delete with all children
                from sqlalchemy import text
                session.execute(
                    text(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT :rid AS id
                            UNION ALL
                            SELECT r.id FROM reckoning r
                            JOIN descendants d ON r.parent_reckoning_id = d.id
                        )
                        DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                        """
                    ),
                    {"rid": rid},
                )
                session.commit()
            else:
                # Non-admin: only delete if no children
                child_count = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.parent_reckoning_id == rid
                    )
                ).first()
                if child_count and child_count > 0:
                    return rx.window_alert(
                        "This concept has comments or votes and cannot be deleted. "
                        "Remove all comments and votes first."
                    )
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
                r.compute_tallies(self.user.id, session=session)

    @rx.var
    def concept_id(self) -> str:
        return self.get_path_param("rid", "no rid")


class CommentsPageState(ReckoningsPageState):
    """The state for the comments page."""

    parent: Optional[Reckoning] = None
    # When non-zero, reckoning_id resolves to this concept id instead of the
    # route's "rid" param. Used by the group page (/group/<slug>), which
    # reuses this state but loads by slug-resolved concept id rather than rid.
    concept_id_override: int = 0

    def close_complete_modal(self):
        yield self.get_reckonings()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Admins can cascade-delete with children;
        non-admins can only delete if the concept has no children."""
        with rx.session() as session:
            if self.user.role >= 2:
                # Admin: cascade delete with all children
                from sqlalchemy import text
                session.execute(
                    text(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT :rid AS id
                            UNION ALL
                            SELECT r.id FROM reckoning r
                            JOIN descendants d ON r.parent_reckoning_id = d.id
                        )
                        DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                        """
                    ),
                    {"rid": rid},
                )
                session.commit()
            else:
                # Non-admin: only delete if no children
                child_count = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.parent_reckoning_id == rid
                    )
                ).first()
                if child_count and child_count > 0:
                    return rx.window_alert(
                        "This concept has comments or votes and cannot be deleted. "
                        "Remove all comments and votes first."
                    )
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
            child.compute_tallies(self.user.id if self.user else None, session=session)
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
                self.parent.compute_tallies(
                    self.user.id if self.user else None, session=session
                )

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
        if self.concept_id_override:
            return str(self.concept_id_override)
        return self.get_path_param("rid", "no rid")


def parent_reckoning(state):
    """The parent reckoning component."""
    if state.parent is None:
        return rx.box()

    support_action = state.vote_on_concept(state.parent.id, ReckoningTypes.up_vote)
    should_pulse = (
        state.show_support_nudge
        & (state.support_nudge_concept_id == state.parent.id)
        & state.support_button_pulsing
    )
    support_button = no_upvote_concept_button(
        on_click=support_action,
        class_name=rx.cond(should_pulse, "support-pulse", ""),
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
            SafeMarkdown.create(
                content=state.parent.content,
                class_name="prose",
                max_width="100%",
                **read_only_text_style,
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
                            (state.parent.user_vote_history == ReckoningTypes.no_vote),
                            rx.fragment(
                                support_button,
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
                            (state.parent.user_vote_history == ReckoningTypes.up_vote),
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
                        SafeMarkdown.create(
                            content=c.parent_content,
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
                            SafeMarkdown.create(
                                content=c.parent_content,
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
                    SafeMarkdown.create(
                        content=c.content,
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
    should_pulse = (
        state.show_support_nudge
        & (state.support_nudge_concept_id == item_id)
        & state.support_button_pulsing
    )
    support_button = no_upvote_concept_button(
        on_click=support_action,
        class_name=rx.cond(should_pulse, "support-pulse", ""),
    )

    return rx.grid(
        rx.box(
            SafeMarkdown.create(
                content=content,
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
                            (state.page_type == 1)
                            | (state.user.role >= 2),
                            delete_button(
                                **popover_button_style,
                                on_click=state.delete_reckoning(item_id),
                            ),
                            disabled_delete_button(**popover_button_style),
                        ),
                        # Graduate button (group pages only, owner only)
                        rx.cond(
                            (state.page_type == 7)
                            & (getattr(state, "is_group_owner", False)),
                            graduate_button(
                                on_click=state.graduate_concept(item_id),
                            ),
                            rx.fragment(),
                        ),
                        rx.fragment(),
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
                    support_button,
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


def page(state, *args, infinite_scroll=False, **kwargs):
    # Infinite-scroll UI (sentinel + hidden trigger) is only emitted for the
    # flat-list pages that implement windowing (_window_query). Pages like
    # Compare/Concept/Comments define their own get_reckonings and must NOT get
    # the sentinel/trigger, or the global observer could click the trigger and
    # reach the base _window_query (NotImplementedError).
    grid_children = [
        rx.foreach(
            state.reckonings,
            lambda r: reckoning(state, r),
        ),
    ]
    trailing = []
    if infinite_scroll:
        grid_children.append(
            # Sentinel: last grid item, full width, so it sits below all cards.
            # Removed once there are no more rows to load.
            rx.cond(
                state.has_more,
                rx.box(
                    id="infinite-scroll-sentinel",
                    width="100%",
                    height="1px",
                    style={"gridColumn": "1 / -1"},
                ),
                rx.fragment(),
            )
        )
        # Hidden button the infinite-scroll observer (assets/scrolling.js)
        # "clicks" to request the next window.
        trailing.append(
            rx.button(
                "Load more",
                id="infinite-load-trigger",
                on_click=state.load_more,
                display="none",
            )
        )

    return container(
        rx.html("""
            <style>
            @keyframes supportPulse {
              0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(1, 204, 93, 0.45); }
              50% { transform: scale(1.08); box-shadow: 0 0 0 14px rgba(1, 204, 93, 0); }
              100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(1, 204, 93, 0); }
            }
            .support-pulse {
              animation: supportPulse 1.2s ease-in-out infinite;
            }
            </style>
            """),
        *args,
        support_nudge_banner(state),
        rx.grid(
            *grid_children,
            h="100vh",
            gap=4,
        ),
        *trailing,
        comment_dialog(),
        concept_dialog(),
        group_dialog(),
        feedback_dialog(options=reckoning_feedback_options),
        **kwargs,
    )


@rx.page(route="/your_concepts", on_load=YourConceptsPageState.on_load, **page_params)
def your_concepts():
    """The your reckonings page."""
    return page(
        YourConceptsPageState,
        navbar(your_concepts_navbar(YourConceptsPageState)),
        infinite_scroll=True,
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
        infinite_scroll=True,
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
        infinite_scroll=True,
    )


@rx.page(route="/new_concepts", on_load=NewConceptsPageState.on_load, **page_params)
def new_concepts():
    """The new concepts page."""
    return page(
        NewConceptsPageState,
        navbar(search_navbar(NewConceptsPageState)),
        infinite_scroll=True,
    )


@rx.page(route="/your_drafts", on_load=YourDraftsPageState.on_load, **page_params)
def your_drafts():
    """The your drafts page."""
    return page(
        YourDraftsPageState,
        navbar(search_navbar(YourDraftsPageState)),
        infinite_scroll=True,
    )


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
