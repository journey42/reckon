"""The authentication state."""
import reflex as rx
from sqlmodel import select
from datetime import datetime, timezone
from .base import AppState, User, Log
from reckon.utils.validations import validate_username, validate_email, validate_password
from reckon.utils.comms import send_password_reset_email

class AuthState(AppState):
    """The authentication state for sign up, register, and login page."""

    email: str
    username: str
    current_password: str
    password: str
    confirm_password: str

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
            
            self.user = User(email=self.email, username=self.username, password=self.password, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
            session.add(self.user)

            log = Log(user_id=self.user.id, content="signed up", type="user", created_at=datetime.now(timezone.utc))
            session.add(log)
            
            session.commit()

            return rx.redirect("/signup_successful")
        
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
            
            user = User(email=self.email, username=self.username, password=self.password, created_at=datetime.now(timezone.utc), updated_at=None)
            session.add(user)

            log = Log(user_id=self.user.id, content="registered", type="user", created_at=datetime.now(timezone.utc))
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

            if user and user.password == self.current_password:
                self.user = user
            else:
                return rx.window_alert("Invalid username or password.")
            
            self.user.password = self.password
            self.user.updated_at = datetime.now(timezone.utc)
            #session.add(self.user)

            log = Log(user_id=self.user.id, content="reset password", type="user", created_at=datetime.now(timezone.utc))
            session.add(log)
            session.commit()

            return rx.redirect("/reset_password_successful")
        
    def request_reset_password(self):
        """Request reset password."""
        with rx.session() as session:
            user = session.exec(
                select(User).where(User.email == self.email)
            ).first()

            result = False

            if user:
                try:
                    result = send_password_reset_email(session, user, "https://reckon.cc/reset_password_via_email")  
                except Exception as e:
                    except_log = Log(user_id=user.id, content=f"password reset failed due to: {str(e)}", type="system", created_at=datetime.now(timezone.utc))
                    session.add(except_log)

                if result:
                    log = Log(user_id=user.id, content="password reset requested", type="user", created_at=datetime.now(timezone.utc))
                    session.add(log)
                else:
                    log = Log(user_id=user.id, content="password reset failed", type="user", created_at=datetime.now(timezone.utc))
                    session.add(log)
                #session.expire_on_commit = False
                session.commit()

                return rx.redirect(f"/reset_password_via_email_request_result/{result}")
            else:
                return rx.window_alert("There is no user with that email address.")

    def reset_password_email_sent(self):
        """Password reset email sent."""
        pass

    def login(self, form_data: dict):
        """Log in a user."""
        with rx.session() as session:
            session.expire_on_commit = False

            self.username = form_data.get("username")
            self.password = form_data.get("password")

            user = session.exec(
                select(User).where(User.username == self.username)
            ).first()
            if user and user.password == self.password:
                if not user.enabled:
                    return rx.window_alert("Account not enabled. We will send you an email when your account is ready.")
                self.user = user

                log = Log(user_id=self.user.id, content="login", type="user", created_at=datetime.now(timezone.utc))
                session.add(log)

                session.commit()

                return rx.redirect("/")
            else:
                return rx.window_alert("Invalid username or password.")
