"""Small shared inline hints for form fields."""

import reflex as rx

from rhiz.utils.validations import password_hint


def password_hint_text() -> rx.Component:
    """Shown under a password field so the rule is visible before someone
    submits, rather than arriving afterwards as a blocking browser popup."""
    return rx.text(
        password_hint(),
        size="1",
        color="#64748b",
        width="100%",
        text_align="left",
        margin_top="-4px",
    )
