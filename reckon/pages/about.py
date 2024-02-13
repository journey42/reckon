"""about page."""
import reflex as rx
from reckon.layouts import info_layout
from reckon.styles import info_text_style
from reckon.state.base import AppState
from reckon.styles import page_params

@rx.page(on_load=AppState.check_login(), **page_params)
def about():
    """The about page."""
    return info_layout(
            rx.text(
                "TODO",
                **info_text_style
            )
    )
