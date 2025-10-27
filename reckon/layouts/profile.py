"""Shared info layout."""

import reflex as rx
from ..components import container, navbar


def profile_layout(*args):
    """The shared layout for profile related pages."""
    return container(
        navbar(),
        rx.box(*args, width="100%"),
        display="flex",
        flex_direction="column",
        align_items="stretch",
        padding_x="24px",
        gap="24px",
    )
