"""reset password successful page."""
import reflex as rx
from reckon.layouts import profile_layout
from reckon.styles import page_params

@rx.page(route="/reset_password_successful", **page_params)
def reset_password_successful():
    """The reset password successful page."""
    return profile_layout(
        rx.text(
            "You your password has been reset.",
            font_size="1xl",
            font_weight="normal",
            mb=4,
        ),
    )
