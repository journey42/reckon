"""'How this works' debate-onboarding overlay.

Greets first-time visitors on a debate (the comments view at /debate/<slug>)
with the debate's title + intro, plus a short explainer. Auto-opens once per
concept via assets/scrolling.js and can be re-summoned from the logged-out
navbar dropdown. Controlled by `show`, mirroring LegendDialogState.
"""

import reflex as rx
from rhiz.state.base import AppState


class HowItWorksDialogState(AppState):
    """'How this works' overlay state."""

    show: bool = False
    debate_title: str = ""
    debate_intro: str = ""

    def visible(self):
        """Toggle the overlay."""
        self.show = not self.show

    @rx.event
    def set_debate_info(self, title: str, intro: str):
        """Populate the greeting with the current debate's title + intro."""
        self.debate_title = title or ""
        self.debate_intro = intro or ""


def how_it_works_dialog(*args, **kwargs):
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.cond(
                    HowItWorksDialogState.debate_title != "",
                    HowItWorksDialogState.debate_title,
                    "How this works",
                ),
            ),
            rx.cond(
                HowItWorksDialogState.debate_intro != "",
                rx.text(
                    HowItWorksDialogState.debate_intro,
                    size="2",
                    style={"whiteSpace": "pre-line", "color": "#475569"},
                    margin_bottom="10px",
                ),
                rx.fragment(),
            ),
            rx.dialog.description(
                "Anyone can read this concept and the responses below. To add a "
                "comment, compare it with similar ideas, or propose your own "
                "alternative, create a free account — your contribution then joins "
                "the wider debate on the site.",
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
