"""Login page. Uses auth_layout to render UI shared with the sign up page.

This is the default auth landing page. When a user comes from a group link,
they see a contextual message about joining that group.
"""

import reflex as rx
from rhiz.layouts import auth_layout
from rhiz.state.auth import AuthState
from rhiz.styles import (
    button_style,
    input_style,
    form_box_style,
    link_style,
    page_params,
)


@rx.page(route="/login", **page_params)
def login():
    """The login page — default entry point for authentication.

    When the URL includes ?next=/group/... it shows a contextual message
    about joining the group.
    """

    return auth_layout(
        rx.cond(
            AuthState.is_group_context,
            rx.callout(
                rx.text(
                    "You're joining a group. Log in with your existing account, "
                    "or create one below.",
                    size="2",
                ),
                color_scheme="blue",
                variant="soft",
            ),
            rx.fragment(),
        ),
        rx.form(
            rx.flex(
                rx.input(
                    name="username",
                    placeholder="Username",
                    on_blur=AuthState.set_username,
                    **input_style,
                ),
                rx.input(
                    name="password",
                    type="password",
                    placeholder="Password",
                    on_blur=AuthState.set_password,
                    **input_style,
                ),
                rx.button(
                    "Log in",
                    type="submit",
                    width="100%",
                    **button_style,
                ),
                **form_box_style,
                direction="column",
                spacing="4",
            ),
            width="100%",
            on_submit=AuthState.login,
        ),
        rx.text(
            rx.link("Forgot password?", href="/request_reset_password", **link_style),
        ),
        rx.text(
            rx.link("Create an account", href="/signup", **link_style),
        ),
    )
