"""profile updated page."""
import reflex as rx
from reckon.layouts import profile_layout
from reckon.styles import page_params
from reckon.state.base import AppState

@rx.page(route="/profile_updated", on_load=AppState.check_login(), **page_params)
def profile_updated():
    """The profile updated page."""
    return profile_layout(
        rx.text(
            "Your profile has been updated.",
            font_size="1xl",
            font_weight="normal",
            mb=4,
        ),
    )
