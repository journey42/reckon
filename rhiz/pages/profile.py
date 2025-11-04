"""profile page."""

import reflex as rx
from rhiz.layouts import profile_layout
from rhiz.state.profile import ProfileState
from rhiz.styles import link_style
from rhiz.styles import button_style
from rhiz.styles import input_style
from rhiz.styles import form_box_style
from rhiz.styles import page_params


@rx.page(on_load=ProfileState.check_login(), **page_params)
def profile():
    """The profile page."""
    return profile_layout(
        rx.center(
            rx.vstack(
                rx.flex(
                    rx.input(
                        default_value=ProfileState.user.email,
                        placeholder="Email",
                        on_blur=ProfileState.set_email,
                        **input_style,
                    ),
                    rx.center(
                        rx.button(
                            "Apply",
                            on_click=ProfileState.update_profile,
                            **button_style,
                        )
                    ),
                    **form_box_style,
                    direction="column",
                    spacing="2",
                ),
                rx.text(
                    rx.link(
                        "Need to reset your password?",
                        href="/reset_password",
                        **link_style,
                    ),
                ),
                spacing="4",
                max_width="480px",
                align_items="center",
            ),
            width="100%",
        ),
    )
