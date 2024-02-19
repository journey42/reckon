"""help page."""
import reflex as rx
from reckon.layouts import info_layout
from reckon.state.base import AppState
from reckon.styles import page_params

def info_page(*args, **kwargs):
    return info_layout(
            rx.text(
                *args,
                font_size="1xl",
                font_weight="normal",
                mb=4,
                border_x="1px solid #ededed",
                h="100%",
            )
    )

help_text = "TODO"

@rx.page(on_load=AppState.check_login(), **page_params)
def help():
    """The help page."""
    return info_page(help_text)

about_text = "TODO"

@rx.page(on_load=AppState.check_login(), **page_params)
def about():
    """The about page."""
    return info_page(about_text)

guidelines_text = "TODO"

@rx.page(on_load=AppState.check_login(), **page_params)
def guidelines():
    """The guidlines page."""
    return info_page(guidelines_text)

terms_text = "TODO"

@rx.page(on_load=AppState.check_login(), **page_params)
def terms():
    """The terms page."""
    return info_page(terms_text)

privacy_text = "TODO"

@rx.page(on_load=AppState.check_login(), **page_params)
def privacy():
    """The privacy page."""
    return info_page(privacy_text)

