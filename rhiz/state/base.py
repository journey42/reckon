"""Base state"""

import os
import reflex as rx
from typing import Optional, List
from sqlmodel import Field, Relationship, select
from sqlalchemy import text
from datetime import datetime
import asyncio
from dataclasses import dataclass
from rhiz.utils.time import calculate_elapsed_time


@dataclass(frozen=True)
class UserTypes:
    """Reckoning types name to index mapping."""

    regular: int = 0
    moderator: int = 1
    admin: int = 2


class User(rx.Model, table=True):
    """A table of Users."""

    username: str = Field()
    password: str = Field()
    email: str = Field()
    enabled: bool = Field(default=False)
    role: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(nullable=True)

    reckonings: List["Reckoning"] = Relationship(back_populates="user")

    logs: List["Log"] = Relationship(back_populates="user")

    feedback: List["Feedback"] = Relationship(back_populates="user")


# from sqlalchemy.types import TypeDecorator, ARRAY
# from sqlalchemy.dialects.postgresql import FLOAT

# class Vector(TypeDecorator):
#     impl = ARRAY(FLOAT)

#     def process_bind_param(self, value, dialect):
#         return value

#     def process_result_value(self, value, dialect):
#         return value


# class TextEmbedding(rx.Model, table=True):
#     id: Optional[int] = Field(default=None, primary_key=True)
#     embedding: List = Field(sa_column=Vector())  # Use 'vector' type for pgvector support
#     reckoning_id: Optional[int] = Field(default=None, foreign_key="reckoning.id")

#     reckoning: Optional["Reckoning"] = Relationship(back_populates="textembedding")


@dataclass(frozen=True)
class ReckoningTypes:
    """Reckoning types name to index mapping."""

    concept: int = 0
    support: int = 1
    detract: int = 2
    point_of_order: int = 3
    draft: int = 4
    up_vote: int = 5
    down_vote: int = 6
    no_vote: int = 7


class Reckoning(rx.Model, table=True):
    """A table of Reckonings."""

    content: str = Field()
    type: int = Field(index=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow, nullable=False, index=True
    )
    updated_at: datetime = Field(nullable=True)

    # textembedding: Optional[TextEmbedding] = Relationship(back_populates="reckoning")

    user_id: int = Field(foreign_key="user.id", nullable=True, index=True)

    user: Optional["User"] = Relationship(back_populates="reckonings")

    parent_reckoning_id: Optional[int] = Field(
        default=None, foreign_key="reckoning.id", index=True
    )

    # Define the relationship with remote_side
    parent_reckoning: Optional["Reckoning"] = Relationship(
        back_populates="child_reckonings",
        sa_relationship_kwargs={"remote_side": "Reckoning.id"},
    )

    child_reckonings: List["Reckoning"] = Relationship(
        back_populates="parent_reckoning", sa_relationship_kwargs={"lazy": "selectin"}
    )

    # temp variable used in rendering
    depth: str = Field(nullable=True)

    # Cache variables, not stored in the database
    supports_detracts_ratio: Optional[str] = None
    up_votes: Optional[int] = 0
    down_votes: Optional[int] = 0
    supports: Optional[int] = 0
    detracts: Optional[int] = 0
    points_of_order: Optional[int] = 0
    total_comments: Optional[int] = 0
    elapsed_time: Optional[str] = ""
    user_vote_history: Optional[int] = ReckoningTypes.no_vote
    similarity: Optional[float] = 0.0
    parent_content: Optional[str] = ""
    parent_type: Optional[int] = 0
    parent_id: Optional[int] = 0
    parent_user_vote_history: Optional[int] = ReckoningTypes.no_vote
    parent_up_votes: Optional[int] = 0
    parent_down_votes: Optional[int] = 0
    parent_supports: Optional[int] = 0
    parent_detracts: Optional[int] = 0
    parent_points_of_order: Optional[int] = 0
    parent_total_comments: Optional[int] = 0
    parent_elapsed_time: Optional[str] = ""

    def cache_parent_details(self, uid: int, session=None):
        try:
            if session is None:
                with rx.session() as sess:
                    self._cache_parent_details_with_session(uid, sess)
            else:
                self._cache_parent_details_with_session(uid, session)
        except Exception:
            pass

    def _cache_parent_details_with_session(self, uid: int, session):
        parent = session.exec(
            select(Reckoning).where(Reckoning.id == self.parent_reckoning_id)
        ).first()
        self.parent_content = parent.content
        self.parent_id = parent.id
        self.parent_type = parent.type
        parent.compute_tallies(uid, session=session)
        if parent.type == ReckoningTypes.concept:
            self.parent_down_votes = parent.down_votes
            self.parent_up_votes = parent.up_votes

            self.parent_user_vote_history = parent.user_vote_history
            self.parent_total_comments = parent.total_comments
        self.parent_supports = parent.supports
        self.parent_detracts = parent.detracts
        self.parent_points_of_order = parent.points_of_order
        self.parent_elapsed_time = calculate_elapsed_time(parent.created_at)

    def tally_child_comments(self, reckoning):
        """
        Recursively counts the total number of child reckonings for a given reckoning instance.

        Parameters:
        - reckoning: Instance of Reckoning

        Returns:
        - int: Total number of children and sub-children reckonings

        NOTE: This walks lazy-loaded relationships and issues one query per
        node (N+1). It is kept only as a fallback when no session is available;
        the hot path uses ``_count_descendant_comments`` instead.
        """
        # Base case: If there are no child reckonings, return 0
        if not reckoning.child_reckonings:
            return 0

        # Recursive case: For each child, count itself plus any of its children
        total_children = 0
        for child in reckoning.child_reckonings:
            # Count the child itself plus any of its children
            if (
                child.type != ReckoningTypes.down_vote
                and child.type != ReckoningTypes.up_vote
            ):
                total_children += 1 + self.tally_child_comments(child)

        return total_children

    def _count_descendant_comments(self, session) -> int:
        """Count all non-vote descendants of this reckoning in a single query.

        Replaces the recursive ``tally_child_comments`` walk (which fired one
        SELECT per node) with a single recursive CTE. Votes are leaf nodes, so
        excluding them is equivalent to the old "don't count, don't recurse"
        behaviour.
        """
        from sqlalchemy import text

        result = session.execute(
            text(
                """
                WITH RECURSIVE descendants AS (
                    SELECT id, type
                    FROM reckoning
                    WHERE parent_reckoning_id = :root
                    UNION ALL
                    SELECT r.id, r.type
                    FROM reckoning r
                    JOIN descendants d ON r.parent_reckoning_id = d.id
                )
                SELECT count(*) FROM descendants
                WHERE type NOT IN (:up_vote, :down_vote)
                """
            ),
            {
                "root": self.id,
                "up_vote": ReckoningTypes.up_vote,
                "down_vote": ReckoningTypes.down_vote,
            },
        ).first()
        return result[0] if result else 0

    def compute_tallies(self, uid: int, session=None) -> int:
        for child in self.child_reckonings:
            if child.type == ReckoningTypes.support:
                self.supports += 1
            elif child.type == ReckoningTypes.detract:
                self.detracts += 1
            elif child.type == ReckoningTypes.up_vote:
                self.up_votes += 1
                if child.user_id == uid:
                    self.user_vote_history = ReckoningTypes.up_vote
            elif child.type == ReckoningTypes.down_vote:
                self.down_votes += 1
                if child.user_id == uid:
                    self.user_vote_history = ReckoningTypes.down_vote
            else:
                self.points_of_order += 1

        if session is not None:
            self.total_comments = self._count_descendant_comments(session)
        else:
            self.total_comments = self.tally_child_comments(self)
        self.elapsed_time = calculate_elapsed_time(self.created_at)
        # # Calculate GCD for simplifying the ratio, avoid division by zero
        # if self.detracts != 0 and self.supports != 0:
        #     ratio_gcd = gcd(self.supports, self.detracts)
        #     simplified_supports = self.supports // ratio_gcd
        #     simplified_detracts = self.detracts // ratio_gcd
        #     ratio = f"{simplified_supports}:{simplified_detracts}"
        # elif self.supports == 0:
        #     ratio = "0:1" if self.detracts != 0 else "0:0"  # Handle case where supports are zero
        # else:
        #     ratio = "N/A"  # If detracts are zero, we can't form a meaningful ratio

        # self.supports_detracts_ratio = f"{self.supports} {ratio} {self.detracts}"

    @staticmethod
    def assign_tallies_batch(reckonings, uid, session):
        """Compute display tallies for a list of concepts in 3 batched queries.

        Equivalent to calling ``compute_tallies`` on each reckoning, but instead
        of per-row round-trips (loading each concept's children + a recursive
        CTE each), it issues three set-based queries for the whole list. Against
        a remote DB this turns ~2 round-trips per row into 3 total.
        """
        if not reckonings:
            return
        ids = [r.id for r in reckonings]
        by_id = {r.id: r for r in reckonings}

        for r in reckonings:
            r.supports = r.detracts = r.up_votes = r.down_votes = 0
            r.points_of_order = 0
            r.total_comments = 0
            r.user_vote_history = ReckoningTypes.no_vote
            r.elapsed_time = calculate_elapsed_time(r.created_at)

        # 1) Direct-child counts grouped by type.
        for pid, ctype, n in session.execute(
            text(
                """
                SELECT parent_reckoning_id, type, count(*)
                FROM reckoning
                WHERE parent_reckoning_id = ANY(:ids)
                GROUP BY parent_reckoning_id, type
                """
            ),
            {"ids": ids},
        ):
            r = by_id.get(pid)
            if r is None:
                continue
            if ctype == ReckoningTypes.support:
                r.supports = n
            elif ctype == ReckoningTypes.detract:
                r.detracts = n
            elif ctype == ReckoningTypes.up_vote:
                r.up_votes = n
            elif ctype == ReckoningTypes.down_vote:
                r.down_votes = n
            else:
                r.points_of_order += n

        # 2) The current user's own vote on each concept (if logged in).
        if uid is not None:
            for pid, ctype in session.execute(
                text(
                    """
                    SELECT parent_reckoning_id, type
                    FROM reckoning
                    WHERE parent_reckoning_id = ANY(:ids)
                      AND user_id = :uid
                      AND type IN (:up, :down)
                    """
                ),
                {
                    "ids": ids,
                    "uid": uid,
                    "up": ReckoningTypes.up_vote,
                    "down": ReckoningTypes.down_vote,
                },
            ):
                r = by_id.get(pid)
                if r is not None:
                    r.user_vote_history = ctype

        # 3) Total non-vote descendants per concept via one recursive CTE.
        for root, n in session.execute(
            text(
                """
                WITH RECURSIVE d AS (
                    SELECT r.id, r.type, r.parent_reckoning_id AS root
                    FROM reckoning r
                    WHERE r.parent_reckoning_id = ANY(:ids)
                    UNION ALL
                    SELECT x.id, x.type, dd.root
                    FROM reckoning x
                    JOIN d dd ON x.parent_reckoning_id = dd.id
                )
                SELECT root, count(*) FILTER (WHERE type NOT IN (:up, :down))
                FROM d
                GROUP BY root
                """
            ),
            {
                "ids": ids,
                "up": ReckoningTypes.up_vote,
                "down": ReckoningTypes.down_vote,
            },
        ):
            r = by_id.get(root)
            if r is not None:
                r.total_comments = n


class Feedback(rx.Model, table=True):
    """A table of Feedback."""

    content: str = Field()
    type: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    subject_reckoning_id: Optional[int] = Field(
        default=None, nullable=True, foreign_key="reckoning.id"
    )

    user_id: int = Field(foreign_key="user.id", nullable=True)

    user: Optional["User"] = Relationship(back_populates="feedback")


class Log(rx.Model, table=True):
    """A table of Logs."""

    content: str = Field()
    type: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    user_id: int = Field(foreign_key="user.id", nullable=True)

    user: Optional["User"] = Relationship(back_populates="logs")


def _is_toolbar_enabled() -> bool:
    """Return True if the editor toolbar should be enabled."""
    value = os.getenv("TOOLBAR_ENABLED", "1")
    return value.strip().lower() not in {"0", "false", "off"}


class AppState(rx.State):
    """The base state for the app."""

    user: Optional[User] = None
    is_running: bool = False
    toolbar_enabled: bool = _is_toolbar_enabled()
    show_support_nudge: bool = False
    support_nudge_concept_id: Optional[int] = None
    nudge_has_matches: bool = False
    support_nudge_collapsed: bool = False
    support_button_pulsing: bool = False

    def scroll_to_saved_position(self):
        return rx.call_script("scrollToSavedPosition();")

    def save_scroll_position(self):
        return rx.call_script("saveScrollPosition();")

    def get_path_param(self, name: str, default: str = "") -> str:
        """Fetch a dynamic route parameter or query parameter."""
        # Prefer explicit query parameters.
        query_value = self.router.url.query_parameters.get(name)  # type: ignore[attr-defined]
        if query_value:
            return query_value

        path_segments = [segment for segment in self.router.url.path.split("/") if segment]  # type: ignore[attr-defined]
        template_segments = [
            segment for segment in self.router.route_id.split("/") if segment
        ]

        for idx, segment in enumerate(template_segments):
            if (
                segment.startswith("[")
                and segment.endswith("]")
                and segment[1:-1] == name
            ):
                if idx < len(path_segments):
                    return path_segments[idx]

        return path_segments[-1] if path_segments else default

    def logout(self):
        """Log out a user."""
        self.reset()
        return rx.redirect("/login")

    def check_login(self):
        """Check if a user is logged in."""
        if (not self.logged_in) or (not self.user.enabled):
            return rx.redirect("/login")
        # return State.check_if_user_enabled

    @rx.var
    def logged_in(self) -> bool:
        """Check if a user is logged in."""
        return self.user is not None

    @rx.event(background=True)
    async def check_if_user_enabled(self):
        """Check if a user is enabled."""
        if self.is_running:
            return
        async with self:
            self.is_running = True
        while True:
            if not self.logged_in:
                print("User is not logged in exiting check_if_user_enabled")
                return

            with rx.session() as session:
                async with self:
                    self.user = session.exec(
                        select(User).where(User.id == self.user.id)
                    ).first()
            if self.user and not self.user.enabled:
                async with self:
                    self.reset()
                    print(
                        "User is not enabled. Resetting and redirecting to /login. Exiting check_if_user_enabled."
                    )
                    return rx.redirect("/login")
            await asyncio.sleep(1)

    # reckonings: list[Reckoning]
    _db_updated: bool = False

    # def load_reckonings(self):
    #     with rx.session() as session:
    #         self.reckonings = session.exec(select(Reckoning)).all()
    #     yield AppState.reload_reckoning

    # @rx.background
    # async def reload_reckonings(self):
    #     while True:
    #         await asyncio.sleep(2)
    #         if self.db_updated:
    #             async with self:
    #                 with rx.session() as session:
    #                     self.reckonings = session.exec(select(Reckoning)).all()
    #                 self._db_updated = False

    @rx.var
    def db_updated(self) -> bool:
        return self._db_updated

    @rx.event
    def set_support_nudge(self, concept_id: int, has_matches: bool = False):
        """Show the support guidance for a just-submitted concept."""
        self.show_support_nudge = True
        self.support_nudge_concept_id = concept_id
        self.nudge_has_matches = has_matches
        self.support_nudge_collapsed = False
        self.support_button_pulsing = True
        yield type(self).start_support_nudge_timers(concept_id=concept_id)

    @rx.event
    def dismiss_support_nudge(self):
        """Hide the post-submission support guidance."""
        self.show_support_nudge = False
        self.support_nudge_concept_id = None
        self.nudge_has_matches = False
        self.support_nudge_collapsed = False
        self.support_button_pulsing = False

    @rx.event
    def collapse_support_nudge(self):
        """Collapse the support nudge banner without dismissing it."""
        if self.show_support_nudge:
            self.support_nudge_collapsed = True

    @rx.event
    def expand_support_nudge(self):
        """Expand the support nudge banner if it is collapsed."""
        if self.show_support_nudge:
            self.support_nudge_collapsed = False

    @rx.event
    def stop_support_nudge_pulse(self):
        """Stop pulsing the support button highlight."""
        self.support_button_pulsing = False

    @rx.event(background=True)
    async def start_support_nudge_timers(self, concept_id: int):
        """Automatically collapse and stop pulsing after short delays."""

        collapse_delay = 6
        pulse_duration = 10

        await asyncio.sleep(collapse_delay)
        async with self:
            if self.show_support_nudge and self.support_nudge_concept_id == concept_id:
                self.support_nudge_collapsed = True

        remaining = pulse_duration - collapse_delay
        if remaining > 0:
            await asyncio.sleep(remaining)

        async with self:
            if self.support_nudge_concept_id == concept_id:
                self.support_button_pulsing = False

    # @rx.var
    # def total(self):
    #     return len(self.reckonings)
