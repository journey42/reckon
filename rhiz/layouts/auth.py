"""The shared layout for the auth pages (login, sign up, logged out)."""

import reflex as rx

from rhiz.components.container import container


def auth_layout(*args, background_color: str = "white"):
    """A single centred column: logo, heading, then the page's own content.

    Centring is done with ``margin: auto`` on the column rather than with
    ``rx.center``. The Radix wrappers only forward the props they declare, so
    ``justify_content``/``margin`` passed to them were silently dropped and the
    420px column sat against the left edge of the 960px container on desktop
    (516px of empty space to its right). The container is a block element, so a
    block child with a max width and auto margins centres reliably.
    """
    return container(
        rx.vstack(
            rx.image(
                src="/logo.svg",
                width="160px",
                height="auto",
            ),
            rx.heading(
                rx.text.strong("Speak Together"),
                size="5",
            ),
            *args,
            spacing="5",
            width="100%",
            max_width="420px",
            align="center",
            style={
                "margin": "0 auto",
                "padding": "64px 16px",
            },
        ),
                    width="100%",
        min_height="100vh",
        background=background_color,
    )
