"""The authentication state."""

import reflex as rx
from sqlmodel import select
from datetime import datetime, timezone
from .base import AppState, User, Log
from rhiz.utils.validations import (
    validate_username,
    validate_email,
    validate_password,
)
import os
from datetime import timedelta
from rhiz.utils.comms import send_password_reset_email, send_verification_email
from rhiz.utils.verification import generate_token, is_debate_origin, TOKEN_TTL_HOURS
from rhiz.utils.security import hash_password, verify_password


class AuthState(AppState):
    """The authentication state for sign up, register, and login page."""

    email: str = ""
    username: str = ""
    current_password: str = ""
    password: str = ""
    confirm_password: str = ""

    @rx.event
    def set_email(self, value: str) -> None:
        self.email = value or ""

    @rx.event
    def set_username(self, value: str) -> None:
        self.username = value or ""

    @rx.event
    def set_password(self, value: str) -> None:
        self.password = value or ""

    @rx.event
    def set_confirm_password(self, value: str) -> None:
        self.confirm_password = value or ""

    @rx.event
    def set_current_password(self, value: str) -> None:
        self.current_password = value or ""

    def signup(self):
        """Sign up a user."""
        with rx.session() as session:
            session.expire_on_commit = False
            is_valid, message = validate_email(self.email)
            if not is_valid:
                return rx.window_alert(message)

            is_valid, message = validate_username(self.username)
            if not is_valid:
                return rx.window_alert(message)

            is_valid, message = validate_password(self.password)
            if not is_valid:
                return rx.window_alert(message)

            if self.password != self.confirm_password:
                return rx.window_alert("Passwords do not match.")

            if session.exec(select(User).where(User.username == self.username)).first():
                return rx.window_alert("Username already exists.")

            if session.exec(select(User).where(User.email == self.email)).first():
                return rx.window_alert("User with that email already exists.")

            nxt = self.router.url.query_parameters.get("next")  # type: ignore[attr-defined]
            debate_origin = is_debate_origin(nxt)

            hashed_password = hash_password(self.password)
            new_user = User(
                email=self.email,
                username=self.username,
                password=hashed_password,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            if debate_origin:
                new_user.verification_token = generate_token()
                new_user.verification_expires_at = datetime.now(
                    timezone.utc
                ) + timedelta(hours=TOKEN_TTL_HOURS)
            session.add(new_user)
            session.add(
                Log(
                    user_id=new_user.id,
                    content="signed up",
                    type="user",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

            if not debate_origin:
                # Normal signup: unchanged (disabled, pending manual approval).
                return rx.redirect("/signup_successful")

            # Debate-origin signup: email a verification link that re-enables
            # the account and returns the user to the debate after login.
            base = os.environ.get(
                "PUBLIC_BASE_URL", "http://localhost:3000"
            ).rstrip("/")
            verify_url = (
                f"{base}/verify_email/{new_user.verification_token}?next={nxt}"
            )
            try:
                send_verification_email(new_user, verify_url)
            except Exception as e:
                session.add(
                    Log(
                        user_id=new_user.id,
                        content=f"verification email failed: {e}",
                        type="system",
                        created_at=datetime.now(timezone.utc),
                    )
                )
                session.commit()
            return rx.redirect("/verify_email_sent")

    def register(self):
        """Register a user."""
        with rx.session() as session:
            session.expire_on_commit = False

            is_valid, message = validate_email(self.email)
            if not is_valid:
                return rx.window_alert(message)

            is_valid, message = validate_username(self.username)
            if not is_valid:
                return rx.window_alert(message)

            is_valid, message = validate_password(self.password)
            if not is_valid:
                return rx.window_alert(message)

            if self.password != self.confirm_password:
                return rx.window_alert("Passwords do not match.")

            if session.exec(select(User).where(User.username == self.username)).first():
                return rx.window_alert("Username already exists.")

            if session.exec(select(User).where(User.email == self.email)).first():
                return rx.window_alert("User with that email already exists.")

            hashed_password = hash_password(self.password)
            user = User(
                email=self.email,
                username=self.username,
                password=hashed_password,
                created_at=datetime.now(timezone.utc),
                updated_at=None,
            )
            session.add(user)

            log = Log(
                user_id=self.user.id,
                content="registered",
                type="user",
                created_at=datetime.now(timezone.utc),
            )
            session.add(log)

            session.commit()

            return rx.redirect("/")

    def reset_password(self):
        """Reset password."""
        with rx.session() as session:
            session.expire_on_commit = False

            is_valid, message = validate_password(self.password)
            if not is_valid:
                return rx.window_alert(message)

            if self.password != self.confirm_password:
                return rx.window_alert("Passwords do not match.")

            user = session.exec(
                select(User).where(User.username == self.username)
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
            self.user = user

            log = Log(
                user_id=user.id,
                content="reset password",
                type="user",
                created_at=datetime.now(timezone.utc),
            )
            session.add(log)
            session.commit()

            return rx.redirect("/reset_password_successful")

    def request_reset_password(self):
        """Request reset password."""
        with rx.session() as session:
            user = session.exec(select(User).where(User.email == self.email)).first()

            result = False

            if user:
                try:
                    result = send_password_reset_email(
                        session, user, "https://rhiz.ai/reset_password_via_email"
                    )
                except Exception as e:
                    except_log = Log(
                        user_id=user.id,
                        content=f"password reset failed due to: {str(e)}",
                        type="system",
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(except_log)

                if result:
                    log = Log(
                        user_id=user.id,
                        content="password reset requested",
                        type="user",
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(log)
                else:
                    log = Log(
                        user_id=user.id,
                        content="password reset failed",
                        type="user",
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(log)
                # session.expire_on_commit = False
                session.commit()

                return rx.redirect(f"/reset_password_via_email_request_result/{result}")
            else:
                return rx.window_alert("There is no user with that email address.")

    def reset_password_email_sent(self):
        """Password reset email sent."""
        pass

    def _post_login_target(self) -> str:
        """Where to send the user after login: ?next=/... if safe, else home."""
        from rhiz.utils.urls import safe_next_path

        return safe_next_path(
            self.router.url.query_parameters.get("next")  # type: ignore[attr-defined]
        ) or "/"

    def login(self, form_data: dict):
        """Log in a user."""
        with rx.session() as session:
            session.expire_on_commit = False

            self.username = form_data.get("username")
            self.password = form_data.get("password")

            user = session.exec(
                select(User).where(User.username == self.username)
            ).first()
            match, needs_upgrade = verify_password(
                self.password, user.password if user else None
            )

            if user and match:
                if needs_upgrade:
                    user.password = hash_password(self.password)
                    session.add(user)
                if not user.enabled:
                    return rx.window_alert(
                        "Account not enabled. We will send you an email when your account is ready."
                    )
                self.user = user

                log = Log(
                    user_id=self.user.id,
                    content="login",
                    type="user",
                    created_at=datetime.now(timezone.utc),
                )
                session.add(log)

                session.commit()

                return rx.redirect(self._post_login_target())
            else:
                return rx.window_alert("Invalid username or password.")
