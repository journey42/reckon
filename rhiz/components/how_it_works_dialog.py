"""'How this works' debate-onboarding overlay.

Shown to logged-out visitors on a debate (the comments page reached via a
/debate/<slug> link). Auto-opens once per concept via assets/scrolling.js and
can be re-summoned from the logged-out navbar dropdown. Controlled by `show`,
mirroring LegendDialogState.
"""

import reflex as rx
from rhiz.state.base import AppState


class HowItWorksDialogState(AppState):
    """'How this works' overlay state."""

    show: bool = False

    def visible(self):
        """Toggle the overlay."""
        self.show = not self.show


def how_it_works_dialog(*args, **kwargs):
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("How this works"),
            rx.dialog.description(
                "This page shows a concept open for debate. Anyone can read it "
                "and the responses below. To add a comment, compare it with "
                "similar ideas, or propose your own alternative, create a free "
                "account — your contribution then joins the wider debate on the "
                "site.",
                size="2",
            ),
            rx.dialog.close(
                rx.button(
                    "Got it",
                    margin_top="12px",
                    on_click=HowItWorksDialogState.visible,
                ),
            ),
            max_width="480px",
        ),
        open=HowItWorksDialogState.show,
        *args,
        **kwargs,
    )
