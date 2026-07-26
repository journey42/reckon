"""Sign up page. Uses auth_layout to render UI shared with the login page."""

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


@rx.page(route="/signup", **page_params)
def signup():
    """The sign up page.

    When arriving from a group link (?next=/group/...), shows a contextual
    message about joining that group after verification.
    """

    return auth_layout(
        rx.cond(
            AuthState.is_group_context,
            rx.callout(
                rx.text(
                    "After signing up and verifying your email, you'll be able "
                    "to log in and join the group.",
                    size="2",
                ),
                color_scheme="blue",
                variant="soft",
            ),
            rx.fragment(),
        ),
        rx.text(
            """Thank you for agreeing to test Rhiz. Rhiz is currently an invite-only platform. Please create an account, and we'll contact you once we're ready to welcome you aboard. By signing up, you agree to keep any information you learn during the testing confidential. This means not sharing details about our forum with others. After an initial small run you will have an opportunity to invite up to 5 people to participate.""",
            font_size="0.75em",
            font_weight="normal",
            margin="1em",
            max_width="600px",
        ),
        rx.flex(
            rx.input(
                placeholder="Email",
                on_blur=AuthState.set_email,
                **input_style,
            ),
            rx.input(
                placeholder="Username",
                on_blur=AuthState.set_username,
                **input_style,
            ),
            rx.input(
                type="password",
                placeholder="Password",
                on_blur=AuthState.set_password,
                **input_style,
            ),
            rx.input(
                type="password",
                placeholder="Confirm password",
                on_blur=AuthState.set_confirm_password,
                **input_style,
            ),
            rx.center(
                rx.button(
                    "Sign up",
                    on_click=AuthState.signup,
                    **button_style,
                )
            ),
            **form_box_style,
            direction="column",
            spacing="2",
        ),
        rx.text(
            rx.link("Already have an account? Log in", href="/login", **link_style),
        ),
    )
