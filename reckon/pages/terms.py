"""terms page."""
import reflex as rx
from reckon.layouts import info_layout
from reckon.styles import info_text_style, page_params
from reckon.state.base import AppState

@rx.page(on_load=AppState.check_login(), **page_params)
def terms():
    """The terms page."""
    return info_layout(
            rx.text(
                "TODO",
                **info_text_style
            )
    )
