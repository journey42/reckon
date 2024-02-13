"""Shared info layout."""
import reflex as rx
from ..components import container
from ..components import navbar

def info_layout(*args):
    """The shared layout for info related pages."""
    return container(
        navbar(),
        rx.grid(
            *args,
            grid_template_columns="1fr",
            h="100vh",
            gap=4,
        ),
        max_width="1300px",
    )
