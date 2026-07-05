"""'How this works' group-onboarding overlay.

Greets first-time visitors on a group page (the comments view at /group/<slug>)
with the group's name + founding question, plus a short explainer. Auto-opens
once per visit via assets/scrolling.js and can be re-summoned from the
logged-out navbar dropdown. Controlled by `show`, mirroring LegendDialogState.
"""

import reflex as rx
from rhiz.state.base import AppState


class HowItWorksDialogState(AppState):
    """'How this works' overlay state."""

    show: bool = False
    group_name: str = ""
    founding_question: str = ""

    def visible(self):
        """Toggle the overlay."""
        self.show = not self.show

    @rx.event
    def set_group_info(self, name: str, founding_question: str):
        """Populate the greeting with the current group's name + founding question."""
        self.group_name = name or ""
        self.founding_question = founding_question or ""


def how_it_works_dialog(*args, **kwargs):
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.cond(
                    HowItWorksDialogState.founding_question != "",
                    f"How this works: {HowItWorksDialogState.group_name}",
                    "How this works",
                ),
            ),
            rx.text(
                (
                    "This is a pilot to allow groups to find consensus. To "
                    "participate just answer the founding question your group "
                    "has posed in your own words or upvote existing answers. "
                    "If you get lost you can always return to your groups home "
                    "page (link or QR code).\n\n"
                    "The ideas you submit will be ranked by semantic similarity "
                    "with other submissions in your group. When you submit an "
                    "idea any related ideas that have been submitted to the "
                    "group will display below, starting with your idea at the "
                    "top.\n\n"
                    "If someone has entered something similar you can either "
                    "choose to stick with your language and confirm your "
                    "submission or switch your support to the other statement. "
                    "This allows emergent consensus to coalesce. The pipeline "
                    "that compares idea submissions does not apply to the "
                    "comments section. The comments are plain text and you "
                    "submit them along with a green, yellow or red button "
                    "conveying agreement, a neutral note, or disagreement."
                ),
                size="2",
                style={"whiteSpace": "pre-line", "color": "#475569"},
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
