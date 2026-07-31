"""The state for the profile page."""

import reflex as rx
from sqlmodel import select
from datetime import datetime, timezone
from .base import AppState, CurrentUser, User, Log
from rhiz.utils.validations import validate_email, validate_password
from rhiz.utils.security import hash_password, verify_password
from rhiz.utils.sessions import revoke_all_for_user


class ProfileState(AppState):
    email: str = ""
    current_password: str = ""
    password: str = ""
    confirm_password: str = ""

    @rx.event
    def set_email(self, value: str) -> None:
        self.email = value or ""

    @rx.event
    def set_current_password(self, value: str) -> None:
        self.current_password = value or ""

    @rx.event
    def set_password(self, value: str) -> None:
        self.password = value or ""

    @rx.event
    def set_confirm_password(self, value: str) -> None:
        self.confirm_password = value or ""

    def reset_password(self):
        """Reset password."""
        if not self.logged_in:
            return rx.redirect("/login")

        with rx.session() as session:
            # Keep `user` readable after the commit below.
            session.expire_on_commit = False

            is_valid, message = validate_password(self.password)
            if not is_valid:
                return rx.window_alert(message)

            if self.password != self.confirm_password:
                return rx.window_alert("Passwords do not match.")

            # Re-read the live row by id; state holds only a snapshot.
            user = session.exec(
                select(User).where(User.id == self.user.id)
            ).first()
            match, needs_upgrade = verify_password(
                self.current_password, user.password if user else None
            )
            if not (user and match):
                return rx.window_alert("Invalid username or password.")

            if needs_upgrade:
                user.password = hash_password(self.current_password)

            user.password = hash_password(self.password)
            user.updated_at = datetime.now(timezone.utc)
            session.add(user)

            log = Log(
                user_id=user.id,
                content="password reset",
                type="user",
                created_at=datetime.now(timezone.utc),
            )
            session.add(log)
            session.commit()

            # A password change invalidates sessions everywhere else.
            revoke_all_for_user(session, user.id)

        # Issue a fresh session for this browser and refresh the snapshot.
        self.start_session(user)

        return rx.redirect("/reset_password_successful")

    def update_profile(self):
        """Update user."""
        if not self.logged_in:
            return rx.redirect("/login")

        is_valid, message = validate_email(self.email)
        if not is_valid:
            return rx.window_alert(message)

        with rx.session() as session:
            session.expire_on_commit = False

            if session.exec(select(User).where(User.email == self.email)).first():
                return rx.window_alert("User with that email already exists.")

            # State holds a snapshot, so mutate the live row fetched by id.
            user = session.exec(
                select(User).where(User.id == self.user.id)
            ).first()
            if user is None:
                return rx.window_alert(
                    "Your account could not be found. Please log in again."
                )

            user.email = self.email
            session.add(user)

            log = Log(
                user_id=user.id,
                content="email address updated",
                type="user",
                created_at=datetime.now(timezone.utc),
            )
            session.add(log)
            session.commit()

            # Keep the in-state snapshot consistent with the row.
            self.user = CurrentUser.from_user(user)

        return rx.redirect("/profile_updated")
