"""reset page. Uses auth_layout to render UI shared with the login page."""

import reflex as rx
from reckon.layouts import auth_layout
from reckon.state.auth import AuthState
from reckon.styles import (
    link_style,
    button_style,
    input_style,
    form_box_style,
    page_params,
)


@rx.page(route="/reset_password_via_email", **page_params)
def reset_password_via_email():
    """The reset password page."""
    return auth_layout(
        rx.flex(
            rx.input(
                placeholder="Username",
                on_blur=AuthState.set_username,
                **input_style,
            ),
            rx.input(
                type="password",
                placeholder="Current Password",
                on_blur=AuthState.set_current_password,
                **input_style,
            ),
            rx.input(
                type="password",
                placeholder="New Password",
                on_blur=AuthState.set_password,
                **input_style,
            ),
            rx.input(
                type="password",
                placeholder="Confirm New Password",
                on_blur=AuthState.set_confirm_password,
                **input_style,
            ),
            rx.center(
                rx.button(
                    "Reset",
                    on_click=AuthState.reset_password,
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
