"""Base state"""

import os
import reflex as rx
from typing import Optional, List
from sqlmodel import Field, Relationship, select, SQLModel
from sqlalchemy import text, UniqueConstraint
from datetime import datetime
from dataclasses import dataclass
from rhiz.utils.time import calculate_elapsed_time


class Model(SQLModel):
    """Replacement for rx.Model — provides id primary key + config.

    rx.Model is deprecated in Reflex 0.9.2+ and will be removed in 1.0.
    This subclass replicates the same functionality without the deprecation
    warning.
    """

    id: int | None = Field(default=None, primary_key=True)
    model_config = {
        "arbitrary_types_allowed": True,
        "use_enum_values": True,
        "extra": "allow",
    }


@dataclass(frozen=True)
class UserTypes:
    """Reckoning types name to index mapping."""

    regular: int = 0
    moderator: int = 1
    admin: int = 2


class User(Model, table=True):
    """A table of Users."""

    username: str = Field()
    password: str = Field()
    email: str = Field()
    enabled: bool = Field(default=False)
    role: int = Field(default=0)
    can_create_groups: bool = Field(default=False)
    signup_group_slug: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(nullable=True)
    verification_token: Optional[str] = Field(default=None, nullable=True)
    verification_expires_at: Optional[datetime] = Field(default=None, nullable=True)

    reckonings: List["Reckoning"] = Relationship(back_populates="user")

    logs: List["Log"] = Relationship(back_populates="user")

    feedback: List["Feedback"] = Relationship(back_populates="user")

    group_members: List["GroupMember"] = Relationship(back_populates="user")


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


class Reckoning(Model, table=True):
    """A table of Reckonings."""

    content: str = Field()
    type: int = Field(index=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow, nullable=False, index=True
    )
    updated_at: datetime = Field(nullable=True)

    # When non-null, this reckoning belongs to a group and is only visible
    # on that group's page (unless the group is made public).
    group_id: Optional[int] = Field(
        default=None, foreign_key="group.id", nullable=True, index=True
    )
    is_graduated: bool = Field(default=False)

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
    up_votes: int = 0
    down_votes: int = 0
    supports: int = 0
    detracts: int = 0
    points_of_order: int = 0
    total_comments: int = 0
    elapsed_time: str = ""
    user_vote_history: int = ReckoningTypes.no_vote
    similarity: float = 0.0
    parent_content: str = ""
    parent_type: int = 0
    parent_id: int = 0
    parent_user_vote_history: int = ReckoningTypes.no_vote
    parent_up_votes: int = 0
    parent_down_votes: int = 0
    parent_supports: int = 0
    parent_detracts: int = 0
    parent_points_of_order: int = 0
    parent_total_comments: int = 0
    parent_elapsed_time: str = ""

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
            text("""
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
                """),
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
            text("""
                SELECT parent_reckoning_id, type, count(*)
                FROM reckoning
                WHERE parent_reckoning_id = ANY(:ids)
                GROUP BY parent_reckoning_id, type
                """),
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
                text("""
                    SELECT parent_reckoning_id, type
                    FROM reckoning
                    WHERE parent_reckoning_id = ANY(:ids)
                      AND user_id = :uid
                      AND type IN (:up, :down)
                    """),
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
            text("""
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
                """),
            {
                "ids": ids,
                "up": ReckoningTypes.up_vote,
                "down": ReckoningTypes.down_vote,
            },
        ):
            r = by_id.get(root)
            if r is not None:
                r.total_comments = n


@dataclass(frozen=True)
class GroupStatus:
    """Group lifecycle states."""

    open: str = "open"
    closed: str = "closed"


class Group(Model, table=True):
    """A distributable group page with its own concept feed."""

    slug: str = Field(index=True, unique=True)
    concept_id: int = Field(foreign_key="reckoning.id", index=True, unique=True)
    name: str = Field()
    founding_question: str = Field(default="")
    status: str = Field(default=GroupStatus.open)
    is_public: bool = Field(default=False)
    created_by: Optional[int] = Field(
        default=None, foreign_key="user.id", nullable=True
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    members: List["GroupMember"] = Relationship(back_populates="group")


class GroupMember(Model, table=True):
    """Tracks which users belong to which groups.

    Created automatically when a logged-in user visits a group page or
    submits content. Admins can also add members directly by email.
    """

    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    group_id: int = Field(foreign_key="group.id", nullable=False, index=True)
    joined_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    user: Optional["User"] = Relationship(back_populates="group_members")
    group: Optional["Group"] = Relationship(back_populates="members")

    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)


class UserSession(Model, table=True):
    """A persistent login session, keyed by an opaque token held in a cookie.

    Reflex keeps ``AppState.user`` in server-side state, which is lost whenever
    the backend restarts, the state manager evicts the entry, or the browser
    gets a new client token. That is what made users appear to be "kicked out"
    mid-session. This table lets us re-hydrate the logged-in user from a cookie
    so a lost state entry is no longer a logout.

    Only the SHA-256 hash of the token is stored, so a database leak does not
    hand over usable sessions.
    """

    token_hash: str = Field(nullable=False, index=True, unique=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    last_used_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    expires_at: datetime = Field(nullable=False)
    revoked: bool = Field(default=False, nullable=False)


class Feedback(Model, table=True):
    """A table of Feedback."""

    content: str = Field()
    type: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    subject_reckoning_id: Optional[int] = Field(
        default=None, nullable=True, foreign_key="reckoning.id"
    )

    user_id: int = Field(foreign_key="user.id", nullable=True)

    user: Optional["User"] = Relationship(back_populates="feedback")


class Log(Model, table=True):
    """A table of Logs."""

    content: str = Field()
    type: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    user_id: int = Field(foreign_key="user.id", nullable=True)

    user: Optional["User"] = Relationship(back_populates="logs")


class AppSetting(Model, table=True):
    """Simple key-value store for app-wide settings."""

    key: str = Field(primary_key=True)
    value: str = Field(default="")


def get_setting(key: str, default: str = "") -> str:
    """Read a setting from the database."""
    with rx.session() as session:
        row = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
        return row.value if row else default


def set_setting(key: str, value: str) -> None:
    """Write a setting to the database."""
    with rx.session() as session:
        row = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
        if row:
            row.value = value
        else:
            row = AppSetting(key=key, value=value)
        session.add(row)
        session.commit()


def _is_toolbar_enabled() -> bool:
    """Return True if the editor toolbar should be enabled."""
    value = os.getenv("TOOLBAR_ENABLED", "1")
    return value.strip().lower() not in {"0", "false", "off"}


class CurrentUser(SQLModel):
    """An immutable snapshot of the logged-in user, held in state.

    Note: intentionally declared WITHOUT ``table=True`` - it is a plain
    pydantic model with no database identity, mapper or session.

    Deliberately NOT the SQLModel ``User`` table instance. A live ORM object
    stored in Reflex state becomes detached once its session closes, and
    expired the moment any session it belongs to commits - so the next
    attribute read raises ``DetachedInstanceError``. Because that only happens
    on some code paths, it surfaces intermittently and is easy to ship.

    Snapshotting the handful of fields the app actually needs removes that
    whole class of bug: this object never talks to the database.

    Anything needing the live row should re-read it by ``id`` inside a session.
    """

    id: int = 0
    username: str = ""
    email: str = ""
    role: int = 0
    enabled: bool = False
    can_create_groups: bool = False
    signup_group_slug: Optional[str] = None

    @classmethod
    def from_user(cls, user: "User") -> "CurrentUser":
        """Build a snapshot. Must be called while ``user`` is session-bound."""
        return cls(
            id=user.id or 0,
            username=user.username or "",
            email=user.email or "",
            role=user.role or 0,
            enabled=bool(user.enabled),
            can_create_groups=bool(user.can_create_groups),
            signup_group_slug=user.signup_group_slug,
        )


def _is_secure_cookie() -> bool:
    """Send the auth cookie only over HTTPS when deployed.

    Derived from PUBLIC_BASE_URL so local http://localhost testing still works
    while production (https://) gets the Secure flag.
    """
    return os.getenv("PUBLIC_BASE_URL", "http://localhost:3000").startswith("https://")


class AppState(rx.State):
    """The base state for the app."""

    user: Optional[CurrentUser] = None

    # Opaque session token, persisted client-side so that losing server-side
    # state (backend restart, eviction, new client token) is no longer a
    # logout. Only its SHA-256 hash is stored server-side.
    auth_token: str = rx.Cookie(
        "",
        name="rhiz_auth",
        path="/",
        max_age=30 * 24 * 60 * 60,
        same_site="lax",
        secure=_is_secure_cookie(),
    )

    toolbar_enabled: bool = _is_toolbar_enabled()
    show_support_nudge: bool = False
    support_nudge_concept_id: Optional[int] = None
    nudge_has_matches: bool = False
    support_nudge_collapsed: bool = False
    support_button_pulsing: bool = False

    def scroll_to_saved_position(self):
        return rx.call_script("if(typeof scrollToSavedPosition==='function')scrollToSavedPosition();")

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

    def start_session(self, user: User) -> None:
        """Mark ``user`` as logged in and persist the session in a cookie.

        Call this instead of assigning ``self.user`` directly, so the login
        survives a backend restart or a lost state entry.
        """
        from rhiz.utils.sessions import create_session

        # Snapshot before the ORM instance can be expired or detached.
        self.user = CurrentUser.from_user(user)
        with rx.session() as session:
            self.auth_token = create_session(session, self.user.id)

    def _hydrate_user(self) -> bool:
        """Rebuild ``self.user`` from the auth cookie when state was lost.

        Returns True if a user is present afterwards. This is what stops the
        "kicked out mid-interaction" behaviour: a missing state entry is
        recovered from the cookie instead of bouncing to /login.
        """
        if self.user is not None:
            return True
        if not self.auth_token:
            return False

        from rhiz.utils.sessions import resolve_session

        with rx.session() as session:
            user = resolve_session(session, self.auth_token)
            # Snapshot inside the session, while the instance is still bound.
            snapshot = CurrentUser.from_user(user) if user is not None else None

        if snapshot is None:
            # Stale/expired/revoked cookie - clear it so we stop retrying.
            self.auth_token = ""
            return False

        self.user = snapshot
        return True

    def logout(self):
        """Log out a user and revoke the persisted session."""
        from rhiz.utils.sessions import revoke_session

        if self.auth_token:
            with rx.session() as session:
                revoke_session(session, self.auth_token)
        self.reset()
        return rx.redirect("/login")

    def check_login(self):
        """Check if a user is logged in and enabled.

        Attempts cookie-based re-hydration before redirecting, so a lost
        server-side state entry no longer forces a logout.
        """
        self._hydrate_user()
        if not self.logged_in or not self.user.enabled:
            return rx.redirect("/login")
        return None

    @rx.var
    def logged_in(self) -> bool:
        """Check if a user is logged in."""
        return self.user is not None

    @rx.var(auto_deps=False, deps=["user"])
    def posthog_distinct_id(self) -> str:
        """User ID for PostHog cross-device tracking."""
        if self.user:
            return f"user-{self.user.id}"
        return ""

    @rx.var(auto_deps=False, deps=["user"])
    def user_can_manage_groups(self) -> bool:
        """True if the current user may create/manage groups (role or per-user flag).

        Imported lazily + explicit deps because rhiz.utils.permissions imports
        from this module (circular import otherwise breaks auto-dep detection).
        """
        from rhiz.utils.permissions import can_manage_groups

        return can_manage_groups(self.user)

    def check_user_enabled(self):
        """Check if the current user is enabled.

        Replaces the background polling task which caused race conditions and
        lock contention. Called at key points: on_load handlers, before
        write operations, and after login.
        """
        self._hydrate_user()
        if self.logged_in and not self.user.enabled:
            # Disabled account: revoke every session so other devices stop too.
            from rhiz.utils.sessions import revoke_all_for_user

            user_id = self.user.id
            with rx.session() as session:
                revoke_all_for_user(session, user_id)
            self.reset()
            return rx.redirect("/login")
        return None

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
