"""Shared info layout."""

import reflex as rx
from ..components import container, navbar


def info_layout(*args):
    """The shared layout for info related pages."""
    return container(
        navbar(),
        rx.box(
            rx.grid(*args, width="100%", h="100%"),
            width="100%",
            padding="24px",
        ),
        display="flex",
        flex_direction="column",
        align_items="stretch",
        gap="24px",
    )
