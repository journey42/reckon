"""Shared auth layout."""
import reflex as rx
from ..components import container

def auth_layout(*args):
    """The shared layout for auth related pages."""
    return container(
        rx.image(src="/logo.svg", width="40%", height="auto", margin="8px 0 0 0",),
        rx.heading(
            rx.text.strong("Speak Together"),
            size="5",
            margin="0 0 8px 0",
        ),
        *args,
        # border_radius="5px",
        # box_shadow="0 4px 60px 0 rgba(0, 0, 0, 0.08), 0 4px 16px 0 rgba(0, 0, 0, 0.08)",
        display="flex",
        justify_content="center",
        flex_direction="column",
        align_items="center",
        min_height="100vh"
        # padding="12px 12px 0 0",
        # margin="16 0 0 0",
    )
        # height="95vh",
        # margin="16px",
        # background="url(bg.svg)",
        # background_repeat="no-repeat",
        # background_size="cover",
    # )
