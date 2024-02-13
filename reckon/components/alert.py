"""Alert dialog component."""

import reflex as rx
from reckon.state.base import AppState

class AlertDialogState(AppState):
    """Alert dialog state."""
    show: bool = False

    def change(self):
        """Change the visibility of the alert dialog."""
        self.show = not (self.show)


def alert_dialog(header: str, body: str, button: str):
    """An alert dialog."""
    return rx.vstack(
        rx.alert_dialog(
            rx.alert_dialog_overlay(
                rx.alert_dialog_content(
                    rx.alert_dialog_header(header),
                    rx.alert_dialog_body(
                        body
                    ),
                    rx.alert_dialog_footer(
                        rx.button(
                            button,
                            on_click=AlertDialogState.change,
                        )
                    ),
                )
            ),
            is_open=AlertDialogState.show,
        ),
        width="100%",
    )