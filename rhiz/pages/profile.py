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
    box_props = {**form_box_style, "max_width": "640px", "width": "100%"}
    return profile_layout(
        rx.center(
            rx.vstack(
                rx.flex(
                    rx.input(
                        default_value=ProfileState.user.email,
                        placeholder="Email",
                        on_blur=ProfileState.set_email,
                        font_size="2",
                        **input_style,
                        padding_x="8px",
                    ),
                    rx.center(
                        rx.button(
                            "Apply",
                            on_click=ProfileState.update_profile,
                            **button_style,
                        )
                    ),
                    **box_props,
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
                max_width="640px",
                align_items="center",
            ),
            width="100%",
            min_height="70vh",
        ),
    )
