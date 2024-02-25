"""profile updated page."""
import reflex as rx
from reckon.layouts import profile_layout
from reckon.styles import page_params, info_text_style
from reckon.state.base import AppState

@rx.page(route="/profile_updated", on_load=AppState.check_login(), **page_params)
def profile_updated():
    """The profile updated page."""
    return profile_layout(
        rx.text(
            "Your profile has been updated.",
            **info_text_style
        ),
    )
