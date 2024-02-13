"""profile page. """
import reflex as rx
from reckon.layouts import profile_layout
from reckon.state.profile import ProfileState
from reckon.styles import link_style
from reckon.styles import button_style
from reckon.styles import input_style
from reckon.styles import form_box_style
from reckon.styles import page_params

@rx.page(on_load=ProfileState.check_login(), **page_params)
def profile():
    """The profile page."""
    return profile_layout(
        rx.box(
            rx.hstack(
                rx.text("Email: ", font_size="1xl", font_weight="normal"),
                rx.input(
                    default_value=ProfileState.user.email,
                    placeholder="Email",
                    on_blur=ProfileState.set_email,
                    **input_style,
                ),
                mb=4,
            ),
            rx.center(
                rx.button(
                    "Apply",
                    on_click=ProfileState.update_profile,
                    **button_style,
                )
            ),
            **form_box_style,
        ),
        rx.text(
            rx.link("Need to reset your password?", href="/reset_password", **link_style),
        ),
    )
