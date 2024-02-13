"""Shared info layout."""
import reflex as rx
from ..components import container
from ..components import navbar

def profile_layout(*args):
    """The shared layout for profile related pages."""
    return container(
            navbar(),
            *args,
            display="flex",
            flex_direction="column",
            align_items="center",
            gap=4,
            max_width="1300px",
        )
