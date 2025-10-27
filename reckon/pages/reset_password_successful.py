"""reset password successful page."""

import reflex as rx
from reckon.layouts import profile_layout
from reckon.styles import page_params, info_text_style


@rx.page(route="/reset_password_successful", **page_params)
def reset_password_successful():
    """The reset password successful page."""
    return profile_layout(
        rx.text("You your password has been reset.", **info_text_style),
    )
