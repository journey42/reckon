"""The state for the profile page."""
import reflex as rx
from sqlmodel import select
from datetime import datetime, timezone
from .base import AppState,  User, Log
from reckon.utils.validations import validate_email, validate_password
from reckon.utils.security import hash_password, verify_password

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
        with rx.session() as session:
            is_valid, message = validate_password(self.password)
            if not is_valid:
                return rx.window_alert(message)

            if self.password != self.confirm_password:
                return rx.window_alert("Passwords do not match.")
            
            user = session.exec(
                select(User).where(User.username == self.user.username)
            ).first()
            match, needs_upgrade = verify_password(self.current_password, user.password if user else None)
            if not (user and match):
                return rx.window_alert("Invalid username or password.")

            if needs_upgrade:
                user.password = hash_password(self.current_password)

            user.password = hash_password(self.password)
            user.updated_at = datetime.now(timezone.utc)
            session.add(user)
            self.user = user
            
            log = Log(user_id=self.user.id, content="password reset", type="user", created_at=datetime.now(timezone.utc))
            session.add(log)
            #session.expire_on_commit = False
            session.commit()

            return rx.redirect("/reset_password_successful")


    def update_profile(self):
            """Update user."""
            is_valid, message = validate_email(self.email)
            if not is_valid:
                return rx.window_alert(message)
            
            with rx.session() as session:
                if session.exec(select(User).where(User.email == self.email)).first():
                    return rx.window_alert("User with that email already exists.")
                self.user.email = self.email
                session.add(self.user)

                log = Log(user_id=self.user.id, content="email address updated", type="user", created_at=datetime.now(timezone.utc))
                session.add(log)
                #session.expire_on_commit = False
                session.commit()

                return rx.redirect("/profile_updated")
