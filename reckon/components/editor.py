"""Editor component helpers."""

import uuid

import reflex as rx

def editor(*args, **kwargs) -> rx.Component:
    """Return a plain textarea for simple text capture."""
    props = {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "rows": kwargs.pop("rows", "10"),
        "width": kwargs.pop("width", "100%"),
        "resize": kwargs.pop("resize", "vertical"),
        "padding": kwargs.pop("padding", "12px"),
    }
    props.update(kwargs)
    return rx.text_area(*args, **props)


def rich_text_editor(*args, **kwargs) -> rx.Component:
    """Fallback rich text editor using a simple textarea."""
    return editor(*args, **kwargs)
