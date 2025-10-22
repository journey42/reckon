"""Shared auth layout."""
import reflex as rx
from ..components import container

def auth_layout(*args, background_color: str = "white"):
    """The shared layout for auth related pages."""
    return container(
        rx.center(
            rx.vstack(
                rx.image(
                    src="/logo.svg",
                    width="160px",
                    height="auto",
                ),
                rx.heading(
                    rx.text.strong("Speak Together"),
                    size="5",
                ),
                *args,
                spacing="5",
                width="100%",
                max_width="420px",
                align="center",
            ),
            width="100%",
            padding="64px 16px",
        ),
        display="flex",
            justify_content="center",
            flex_direction="column",
            align_items="center",
            min_height="100vh",
            background=background_color,
        )
