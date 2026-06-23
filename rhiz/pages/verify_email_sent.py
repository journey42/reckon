"""Confirmation shown after a debate-origin signup sends a verification email."""

import reflex as rx
from rhiz.components.container import container
from rhiz.styles import page_params


@rx.page(route="/verify_email_sent", **page_params)
def verify_email_sent():
    return container(
        rx.center(
            rx.vstack(
                rx.heading("Check your email", size="6"),
                rx.text(
                    "We've sent you a link to verify your email and activate "
                    "your account. Open it, then log in to join the debate.",
                    size="3",
                ),
                rx.link("Back to login", href="/login"),
                spacing="3",
                align="center",
            ),
            min_height="60vh",
        ),
    )
