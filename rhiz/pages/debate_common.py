"""Shared building blocks for the debate management pages.

Both the admin all-debates view (/debates) and the per-user view
(/your_debates) render the same kind of row (share link + QR, open/close,
delete) and compute the same public share URL. The only differences are which
debates each lists and who may see the page, so those live in the page modules
while the common rendering lives here.
"""

import os
import reflex as rx

from rhiz.state.base import DebateStatus


def public_base_url() -> str:
    """Public origin for debate share links. Set PUBLIC_BASE_URL in production
    (e.g. https://www.rhiz.ai); defaults to the local dev frontend. Trailing
    slash is stripped."""
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:3000").rstrip("/")


def debate_row(state_cls, r):
    """A single debate card. `state_cls` is the page's State class so the
    open/close and delete actions dispatch to that page's handlers.

    Uses a responsive flex: a row on desktop, but stacked into a column on
    small screens so the Close/Delete buttons stay fully visible and tappable
    instead of being clipped off the right edge.
    """
    return rx.card(
        rx.flex(
            rx.vstack(
                rx.heading(r["title"], size="3"),
                rx.link(r["url"], href=r["url"], size="1"),
                rx.text("Status: ", r["status"], size="1"),
                rx.cond(
                    r["creator"] != "",
                    rx.text("Created by: ", r["creator"], size="1", color="gray"),
                    rx.fragment(),
                ),
                align="start",
                spacing="1",
                flex_grow="1",
                min_width="0",
            ),
            rx.image(
                src=r["qr"], width="96px", height="96px", flex_shrink="0"
            ),
            rx.vstack(
                rx.button(
                    rx.cond(r["status"] == DebateStatus.open, "Close", "Reopen"),
                    on_click=state_cls.toggle_status(r["id"], r["status"]),
                    variant="soft",
                    size="1",
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                rx.button(
                    "Delete",
                    on_click=state_cls.delete_debate(r["id"]),
                    color_scheme="red",
                    variant="soft",
                    size="1",
                    width=rx.breakpoints(initial="100%", sm="auto"),
                ),
                spacing="2",
                width=rx.breakpoints(initial="100%", sm="auto"),
                flex_shrink="0",
            ),
            direction=rx.breakpoints(initial="column", sm="row"),
            align=rx.breakpoints(initial="stretch", sm="center"),
            wrap="wrap",
            gap="12px",
            width="100%",
        ),
        width="100%",
    )
