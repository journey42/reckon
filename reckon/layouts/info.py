"""Shared info layout."""
import reflex as rx
from ..components import container, navbar

def info_layout(*args):
    """The shared layout for info related pages."""
    return container(
        navbar(),
        rx.grid(
            *args,
            h="100vh",
            gap=4,
        ),
    )
