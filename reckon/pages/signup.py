"""Sign up page. Uses auth_layout to render UI shared with the login page."""
import reflex as rx
from reckon.layouts import auth_layout
from reckon.state.auth import AuthState
from reckon.styles import button_style, input_style, form_box_style, link_style, page_params

@rx.page(**page_params)
def signup():
    """The sign up page."""
    return auth_layout(
        rx.text(
            "Reckon is currently an invite-only platform. Please create an account, and we'll contact you once we're ready to welcome you aboard.",
            font_size="1xl",
            font_weight="normal",
            mb=4,
        ),
        rx.box(
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
                type_="password",
                placeholder="Password",
                on_blur=AuthState.set_password,
                **input_style,
            ),
            rx.input(
                type_="password",
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
            **form_box_style
        ),
        rx.text(
            rx.link("Already have an account?", href="/login", **link_style),
        ),
    )
