"""Base state"""
import reflex as rx
from typing import Optional, List
from sqlmodel import Field, Relationship, select
from datetime import datetime
import asyncio
from dataclasses import dataclass
from math import gcd

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

    reckonings: List["Reckoning"] = Relationship(
        back_populates="user"
    )

    logs: List["Log"] = Relationship(
        back_populates="user"
    )
    
    feedback: List["Feedback"] = Relationship(
        back_populates="user"
    )

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

class Reckoning(rx.Model, table=True):
    """A table of Reckonings."""

    content: str = Field()
    type: int = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(nullable=True)

    # textembedding: Optional[TextEmbedding] = Relationship(back_populates="reckoning")
    
    user_id: int = Field(foreign_key="user.id", nullable=True)

    user: Optional["User"] = Relationship(
        back_populates="reckonings"
    )

    parent_reckoning_id: Optional[int] = Field(
        default=None,
        foreign_key="reckoning.id"
    )

    # Define the relationship with remote_side
    parent_reckoning: Optional["Reckoning"] = Relationship(
        back_populates="child_reckonings",
        sa_relationship_kwargs={"remote_side":"Reckoning.id"}
    )
    
    child_reckonings: List["Reckoning"] = Relationship(
        back_populates="parent_reckoning",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    # Cache variables, not stored in the database
    supports_detracts_ratio: Optional[str] = None
    up_votes: Optional[int] = 0
    down_votes: Optional[int] = 0
    supports: Optional[int] = 0
    detracts: Optional[int] = 0
    points_of_order: Optional[int] = 0
    total_comments: Optional[int] = 0
    user_vote_history: Optional[int] = 0
    similarity: Optional[float] = 0.0
    parent_content: Optional[str] = ""

    def cache_parent_content(self):
        try:
            with rx.session() as session:
                # session.expire_on_commit = False
                self.parent_content = session.exec(select(Reckoning).where(Reckoning.id == self.parent_reckoning_id)).first().content
        except:
            pass


    def tally_children(self, reckoning):
        """
        Recursively counts the total number of child reckonings for a given reckoning instance.
        
        Parameters:
        - reckoning: Instance of Reckoning
        
        Returns:
        - int: Total number of children and sub-children reckonings
        """
        # Base case: If there are no child reckonings, return 0
        if not reckoning.child_reckonings:
            return 0

        # Recursive case: For each child, count itself plus any of its children
        total_children = 0
        for child in reckoning.child_reckonings:
            # Count the child itself plus any of its children
            if child.content != "":
                total_children += 1 + self.tally_children(child)

        return total_children

    def compute_tallies(self, uid: int) -> int:
        for child in self.child_reckonings:
            is_vote = child.content == ""
            if child.type == ReckoningTypes.support:
                if is_vote:
                    self.up_votes+=1
                else:
                    self.supports+=1
                if child.user_id == uid and is_vote:
                    self.user_vote_history = ReckoningTypes.support
            elif child.type == ReckoningTypes.detract:
                if is_vote:
                    self.down_votes+=1
                else:
                    self.detracts+=1
                if child.user_id == uid and is_vote:
                    self.user_vote_history = ReckoningTypes.detract
            else:
                self.points_of_order+=1
                if child.user_id == uid and is_vote:
                    self.user_vote_history = ReckoningTypes.point_of_order
        
        self.total_comments = self.tally_children(self)
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

  
class Feedback(rx.Model, table=True):
    """A table of Feedback."""

    content: str = Field()
    type: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    subject_reckoning_id: Optional[int] = Field(
        default=None,
        nullable=True,
        foreign_key="reckoning.id"
    )
    
    user_id: int = Field(
        foreign_key="user.id",
        nullable=True
    )

    user: Optional["User"] = Relationship(
        back_populates="feedback"
    )

class Log(rx.Model, table=True):
    """A table of Logs."""

    content: str = Field()
    type: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    user_id: int = Field(foreign_key="user.id", nullable=True)

    user: Optional["User"] = Relationship(
        back_populates="logs"
    )       


class AppState(rx.State):
    """The base state for the app."""

    user: Optional[User] = None
    is_running: bool = False

    def logout(self):
        """Log out a user."""
        self.reset()
        return rx.redirect("/login")

    def check_login(self):
        """Check if a user is logged in."""
        if (not self.logged_in) or (not self.user.enabled):
            return rx.redirect("/login")
        #return State.check_if_user_enabled

    @rx.var
    def logged_in(self):
        """Check if a user is logged in."""
        return self.user is not None
    
    @rx.background
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
                    self.user = session.exec(select(User).where(User.id == self.user.id)).first()
            if self.user and not self.user.enabled:
                async with self:
                    self.reset()
                    print("User is not enabled. Resetting and redirecting to /login. Exiting check_if_user_enabled.")
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
    def db_updated(self):
        return self._db_updated

    # @rx.var
    # def total(self):
    #     return len(self.reckonings)
