"""register page. Uses auth_layout to render UI shared with the login page."""

import reflex as rx
from rhiz.layouts import auth_layout
from rhiz.state.auth import AuthState
from rhiz.styles import button_style
from rhiz.styles import input_style
from rhiz.styles import form_box_style
from rhiz.styles import link_style
from rhiz.styles import page_params


@rx.page(**page_params)
def register():
    """The register page."""
    return auth_layout(
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
                    "Register",
                    on_click=AuthState.register,
                    **button_style,
                )
            ),
            **form_box_style,
            direction="column",
            spacing="2",
        ),
        rx.text(
            rx.link("Already have an account?", href="/login", **link_style),
        ),
    )
