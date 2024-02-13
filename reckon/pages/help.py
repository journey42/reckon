"""help page."""
import reflex as rx
from reckon.layouts import info_layout
from reckon.state.base import AppState
from reckon.styles import page_params

@rx.page(on_load=AppState.check_login(), **page_params)
def help():
    """The help page."""
    return info_layout(
            rx.text(
                "TODO",
                font_size="1xl",
                font_weight="normal",
                mb=4,
                border_x="1px solid #ededed",
                h="100%",
            )
    )
