"""password reset via email successful page."""
import reflex as rx
from reckon.layouts import auth_layout
from reckon.styles import link_style, page_params, info_text_style

@rx.page(route="/reset_password_via_email_successful", **page_params)
def reset_password_via_email_successful():
    """The password reset via email successful page."""
    return auth_layout(
        rx.text(
            "You your password has been reset.",
            **info_text_style,
        ),
        rx.text(
            rx.link("Ready to login?", href="/login", **link_style),
        )
    )
