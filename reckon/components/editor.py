"""Editor component

Reflex 0.8.x removed the `rx.editor` rich text widget we previously relied on.
Expose a lightweight wrapper that falls back to a textarea so existing call
sites keep working without bringing in extra dependencies.
"""

import reflex as rx
import uuid


def editor(*args, **kwargs) -> rx.Component:
    """Return a text area with sensible defaults."""
    props = {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "rows": kwargs.pop("rows", "10"),
        "width": kwargs.pop("width", "100%"),
        "resize": kwargs.pop("resize", "vertical"),
        "padding": kwargs.pop("padding", "12px"),
    }
    props.update(kwargs)
    return rx.text_area(*args, **props)
