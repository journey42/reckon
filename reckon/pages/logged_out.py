"""logged out page. Uses auth_layout to render UI shared with the login page."""
import reflex as rx
from reckon.layouts import auth_layout
from reckon.state.auth import AuthState
from reckon.styles import link_style

@rx.page(route="/logged_out", on_load=AuthState.logout())
def logged_out():
    """The logged_out page."""
    return auth_layout(
        rx.text(
            "You have been logged out.",
            font_size="1xl",
            font_weight="normal",
            mb=4,
        ),
        rx.text(
            rx.link("Want back in?", href="/login", **link_style),
        )
    )
