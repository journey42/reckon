"""request reset password page. Uses auth_layout to render UI shared with the login page."""

import reflex as rx
from rhiz.layouts import auth_layout
from rhiz.state.auth import AuthState
from rhiz.styles import (
    button_style,
    input_style,
    form_box_style,
    link_style,
    page_params,
    info_text_style,
)


@rx.page(route="/request_reset_password", **page_params)
def request_reset_password():
    """The request reset password page."""
    return auth_layout(
        rx.text(
            "Enter your email address and we'll send you email with instructions to reset your password.",
            **info_text_style,
        ),
        rx.flex(
            rx.input(
                placeholder="Email",
                on_blur=AuthState.set_email,
                **input_style,
            ),
            rx.center(
                rx.button(
                    "Request Reset",
                    on_click=AuthState.request_reset_password,
                    **button_style,
                )
            ),
            **form_box_style,
            direction="column",
            spacing="2",
        ),
        rx.text(
            rx.link("Change your mind?", href="/login", **link_style),
        ),
    )
