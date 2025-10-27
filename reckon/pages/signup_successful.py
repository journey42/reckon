"""signup successful page. Uses auth_layout to render UI shared with the login page."""

import reflex as rx
from reckon.layouts import auth_layout
from reckon.styles import page_params, info_text_style


@rx.page(route="/signup_successful", **page_params)
def signup_successful():
    """The signup successful page."""
    return auth_layout(
        rx.text(
            "You have successfully signed up for the waitlist. We will email you when it is your time to join.",
            **info_text_style
        )
    )
