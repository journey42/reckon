"""Create-group modal, opened from the Your Groups page.

Unlike the old debate dialog (which wrapped an existing concept), this creates
a standalone group with its own founding question. The user enters a name and
the founding question; a new concept is created to hold the question, and a
Group record links to it.
"""

import reflex as rx

from rhiz.state.base import AppState
from rhiz.utils.groups import create_group
from rhiz.utils.permissions import can_manage_groups


class GroupDialogState(AppState):
    """State for the create-group dialog."""

    show: bool = False
    name: str = ""
    founding_question: str = ""
    error: str = ""

    @rx.event
    def open(self):
        """Open the dialog empty."""
        self.name = ""
        self.founding_question = ""
        self.error = ""
        self.show = True

    @rx.event
    def close(self):
        self.show = False

    @rx.event
    def set_name(self, value: str) -> None:
        self.name = value or ""

    @rx.event
    def set_founding_question(self, value: str) -> None:
        self.founding_question = value or ""

    @rx.event
    def submit(self):
        """Validate and create the group, then go to the management page."""
        self.error = ""
        if not can_manage_groups(self.user):
            self.error = "You do not have permission to create groups."
            return
        if not self.name.strip():
            self.error = "Group name is required."
            return
        if not self.founding_question.strip():
            self.error = "Founding question is required."
            return
        with rx.session() as session:
            try:
                create_group(
                    session,
                    self.name.strip(),
                    self.founding_question.strip(),
                    self.user.id,
                )
            except ValueError as ex:
                self.error = str(ex)
                return
        self.show = False
        return rx.redirect("/your_groups")


def group_dialog(*args, **kwargs):
    """The create-group modal component."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Create Group"),
                rx.input(
                    placeholder="Group name",
                    value=GroupDialogState.name,
                    on_change=GroupDialogState.set_name,
                ),
                rx.text_area(
                    placeholder="Founding question",
                    value=GroupDialogState.founding_question,
                    on_change=GroupDialogState.set_founding_question,
                ),
                rx.cond(
                    GroupDialogState.error != "",
                    rx.callout(
                        GroupDialogState.error, color_scheme="red", size="1"
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            on_click=GroupDialogState.close,
                        ),
                    ),
                    rx.button("Create group", on_click=GroupDialogState.submit),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                align="stretch",
                width="100%",
            ),
            max_width="480px",
        ),
        open=GroupDialogState.show,
        *args,
        **kwargs,
    )
