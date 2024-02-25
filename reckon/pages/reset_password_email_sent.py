"""password reset email sent page. Uses auth_layout to render UI shared with the login page."""
import reflex as rx
from reckon.layouts import auth_layout
from reckon.styles import page_params, info_text_style

@rx.page(route="/reset_password_email_sent", **page_params)
def reset_password_email_sent():
    """The password reset email sent page."""
    return auth_layout(
        rx.text(
            "You have been sent an email with instructions to reset your password.",
            **info_text_style
        )
    )
