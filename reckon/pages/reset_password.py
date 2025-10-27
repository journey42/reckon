"""reset password page."""

import reflex as rx
from reckon.layouts import profile_layout
from reckon.state.profile import ProfileState
from reckon.styles import link_style
from reckon.styles import button_style
from reckon.styles import input_style
from reckon.styles import form_box_style
from reckon.styles import page_params


@rx.page(route="/reset_password", on_load=ProfileState.check_login(), **page_params)
def reset_password():
    """The reset password page."""
    return profile_layout(
        rx.flex(
            rx.input(
                type="password",
                placeholder="Current Password",
                on_blur=ProfileState.set_current_password,
                **input_style,
            ),
            rx.input(
                type="password",
                placeholder="New Password",
                on_blur=ProfileState.set_password,
                **input_style,
            ),
            rx.input(
                type="password",
                placeholder="Confirm New Password",
                on_blur=ProfileState.set_confirm_password,
                **input_style,
            ),
            rx.center(
                rx.button(
                    "Reset",
                    on_click=ProfileState.reset_password,
                    **button_style,
                )
            ),
            **form_box_style,
            direction="column",
            spacing="2",
        ),
        rx.text(
            rx.link("Second thoughts?", href="/", **link_style),
        ),
    )
