"""Login page. Uses auth_layout to render UI shared with the sign up page."""
import reflex as rx
from reckon.layouts import auth_layout
from reckon.state.auth import AuthState
from reckon.styles import button_style, input_style, form_box_style, link_style, page_params, page_footer_style

@rx.page(route="/login", **page_params)
def login():
    """The login page."""
    return auth_layout(
        rx.flex(
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
            rx.center(
                rx.button(
                    "Log in",
                    on_click=AuthState.login,
                    **button_style,
                )
            ),
            **form_box_style,
            direction="column",
            spacing="2",
        ),
        rx.text(
            rx.link("Forgot password?", href="/request_reset_password", **link_style),
        ),
        rx.text(
            rx.link("Don't have an account yet?", href="/signup", **link_style),
        ),
        #rx.text("Copyright 2024 - Reckon Forum LLC.", **page_footer_style)
    )
