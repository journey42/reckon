"""Confirmation shown after a group-origin signup sends a verification email."""

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
                    "your account.",
                    size="3",
                ),
                rx.callout(
                    rx.text(
                        "1. Click the verification link in your email\n"
                        "2. Log in with your credentials\n"
                        "3. You'll be taken to the group page",
                        size="2",
                    ),
                    color_scheme="gray",
                    variant="soft",
                ),
                rx.link("Back to login", href="/login"),
                spacing="3",
                align="center",
            ),
            min_height="60vh",
        ),
    )
