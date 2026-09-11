"""Facilitator dashboard for live Q&A rooms — /live (and admin /live/all).

A room is a private Group in room mode. This dashboard lets any account
holder ask a question (create a room), grab the QR/link, watch the
countdown, extend or close the question, and revisit frozen artifacts.
Before close, answers and results are never shown here — by design.

Admins additionally get /live/all listing every room.
"""

from datetime import datetime

import reflex as rx
from sqlmodel import select, func

from rhiz.state.base import AppState, Group, GroupStatus, Reckoning, RoomParticipant
from rhiz.utils.rooms import (
    DURATION_CHOICES,
    DEFAULT_DURATION_MINUTES,
    DEFAULT_SIMILARITY_THRESHOLD,
    THRESHOLD_CHOICES,
    close_room,
    create_room,
    enforce_deadline,
    extend_room,
)
from rhiz.utils.permissions import can_manage_groups
from rhiz.utils.qr import qr_data_uri
from rhiz.styles import page_params
from rhiz.components import container, navbar
from rhiz.pages.group_common import public_base_url


class LiveState(AppState):
    rows: list[dict] = []

    # Create-room dialog
    show_create: bool = False
    new_question: str = ""
    new_duration: str = "60"
    new_threshold_label: str = "Balanced"
    create_error: str = ""

    # Close dialog (per room)
    show_close_dialog: bool = False
    close_room_id: int = 0
    close_room_name: str = ""
    close_note_input: str = ""
    close_error: str = ""

    @rx.var
    def duration_labels(self) -> list[str]:
        return [f"{m} minutes" for m in [15, 30, 60, 90, 120]]

    def on_load(self):
        result = self.check_user_enabled()
        if result:
            return result
        result = self.check_login()
        if result:
            return result
        self._refresh()

    def _refresh(self):
        self.rows = []
        base = public_base_url()
        with rx.session() as session:
            rooms = session.exec(
                select(Group)
                .where(
                    Group.is_room == True,  # noqa: E712
                    Group.created_by == self.user.id,
                )
                .order_by(Group.created_at.desc())
            ).all()
            for room in rooms:
                room = enforce_deadline(session, room)
                answers = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.group_id == room.id,
                        Reckoning.type == 0,
                        Reckoning.id != room.concept_id,
                    )
                ).one()
                remaining = 0
                if room.status == GroupStatus.open and room.close_at:
                    remaining = max(
                        0,
                        int(
                            (room.close_at - datetime.utcnow()).total_seconds()
                        ),
                    )
                url = f"{base}/room/{room.slug}"
                is_open = room.status == GroupStatus.open
                self.rows.append(
                    {
                        "id": room.id,
                        "slug": room.slug,
                        "question": room.founding_question,
                        "status": room.status,
                        "is_open": is_open,
                        "answers_text": f"{answers} answers",
                        "remaining_text": (
                            f"closes in ~{remaining // 60} min"
                            if is_open and remaining > 0
                            else ""
                        ),
                        "url": url,
                        "qr": qr_data_uri(url),
                        "is_public": room.is_public,
                    }
                )

    # ------------------------------------------------------------------
    # Create room
    # ------------------------------------------------------------------

    def open_create(self):
        self.new_question = ""
        self.new_duration = str(DEFAULT_DURATION_MINUTES)
        self.create_error = ""
        self.show_create = True

    def cancel_create(self):
        self.show_create = False

    def set_new_question(self, value: str):
        self.new_question = value or ""

    def set_new_duration(self, value: str):
        # value arrives as e.g. "60 minutes"
        self.new_duration = (value or "").split()[0] if value else str(DEFAULT_DURATION_MINUTES)

    def confirm_create(self):
        self.create_error = ""
        question = self.new_question.strip()
        if not question:
            self.create_error = "Write the question first."
            return
        try:
            duration = int(self.new_duration)
        except (TypeError, ValueError):
            duration = DEFAULT_DURATION_MINUTES
        with rx.session() as session:
            room = create_room(
                session,
                question,
                self.user.id,
                duration_minutes=duration,
                similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
            )
            slug = room.slug
        self.show_create = False
        self.new_question = ""
        self._refresh()
        return rx.redirect(f"/room/{slug}")

    # ------------------------------------------------------------------
    # Room controls (facilitator)
    # ------------------------------------------------------------------

    def extend(self, room_id: int):
        with rx.session() as session:
            room = session.get(Group, room_id)
            if room is not None and room.created_by == self.user.id:
                extend_room(session, room_id)
        self._refresh()

    def open_close(self, room_id: int):
        with rx.session() as session:
            room = session.get(Group, room_id)
            self.close_room_name = room.founding_question if room else ""
        self.close_room_id = room_id
        self.close_note_input = ""
        self.close_error = ""
        self.show_close_dialog = True

    def cancel_close(self):
        self.show_close_dialog = False

    def set_close_note_input(self, value: str):
        self.close_note_input = value or ""

    def confirm_close(self):
        if not self.close_room_id:
            return
        with rx.session() as session:
            room = session.get(Group, self.close_room_id)
            if room is None or room.created_by != self.user.id:
                return
            close_room(session, room.id, closing_note=self.close_note_input)
        self.show_close_dialog = False
        self._refresh()


class LiveAdminState(LiveState):
    """Admin view: every room, not just mine."""

    def on_load(self):
        result = self.check_user_enabled()
        if result:
            return result
        result = self.check_login()
        if result:
            return result
        if self.user.role < 2:
            return rx.redirect("/")
        self._refresh_all()

    def _refresh_all(self):
        self.rows = []
        base = public_base_url()
        with rx.session() as session:
            rooms = session.exec(
                select(Group)
                .where(Group.is_room == True)  # noqa: E712
                .order_by(Group.created_at.desc())
            ).all()
            for room in rooms:
                room = enforce_deadline(session, room)
                answers = session.exec(
                    select(func.count(Reckoning.id)).where(
                        Reckoning.group_id == room.id,
                        Reckoning.type == 0,
                        Reckoning.id != room.concept_id,
                    )
                ).one()
                url = f"{base}/room/{room.slug}"
                self.rows.append(
                    {
                        "id": room.id,
                        "slug": room.slug,
                        "question": room.founding_question,
                        "status": room.status,
                        "is_open": room.status == GroupStatus.open,
                        "answers_text": f"{answers} answers",
                        "remaining_text": "",
                        "url": url,
                        "qr": "",
                        "is_public": room.is_public,
                    }
                )


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

def _room_row(r: dict, state_cls) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    rx.cond(r["is_open"], "Live", "Closed"),
                    color_scheme=rx.cond(r["is_open"], "green", "gray"),
                    variant="soft",
                ),
                rx.cond(
                    r["remaining_text"] != "",
                    rx.text(r["remaining_text"], size="1", color="#64748b"),
                    rx.fragment(),
                ),
                rx.spacer(),
                rx.text(r["answers_text"], size="1", color="#64748b"),
                spacing="2",
                align="center",
                width="100%",
            ),
            rx.text(r["question"], size="3", weight="medium"),
            rx.hstack(
                rx.cond(
                    r["is_open"],
                    rx.fragment(
                        rx.link("Open room", href=r["url"], size="1"),
                        rx.button(
                            f"Extend +15 min",
                            on_click=state_cls.extend(r["id"]),
                            variant="soft",
                            size="1",
                        ),
                        rx.button(
                            "Close",
                            on_click=state_cls.open_close(r["id"]),
                            color_scheme="red",
                            variant="soft",
                            size="1",
                        ),
                    ),
                    rx.fragment(
                        rx.link("View results", href=r["url"], size="1"),
                    ),
                ),
                spacing="2",
                wrap="wrap",
            ),
            spacing="2",
            align="stretch",
            width="100%",
        ),
        width="100%",
    )


def _create_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Ask a live question"),
                rx.text_area(
                    placeholder="The question — people will answer it in their own words",
                    value=LiveState.new_question,
                    on_change=LiveState.set_new_question,
                    width="100%",
                    min_height="100px",
                ),
                rx.hstack(
                    rx.text("Time limit", size="2", weight="medium"),
                    rx.select(
                        LiveState.duration_labels,
                        value=LiveState.new_duration + " minutes",
                        on_change=LiveState.set_new_duration,
                        size="1",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.callout(
                    "The room closes automatically when the time is up. You "
                    "can extend or close it early at any time. Final results "
                    "are published on this page — nothing is shown before then.",
                    color_scheme="blue",
                    variant="soft",
                    size="1",
                ),
                rx.cond(
                    LiveState.create_error != "",
                    rx.callout(LiveState.create_error, color_scheme="red", size="1"),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            on_click=LiveState.cancel_create,
                        ),
                    ),
                    rx.button("Create room", on_click=LiveState.confirm_create),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                align="stretch",
                width="100%",
            ),
            max_width="520px",
        ),
        open=LiveState.show_create,
    )


def _close_note_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Close question"),
                rx.dialog.description(
                    "Final results will be published on the room page for "
                    "everyone with the link.",
                ),
                rx.text_area(
                    placeholder="Closing note (optional)",
                    value=LiveState.close_note_input,
                    on_change=LiveState.set_close_note_input,
                    width="100%",
                    min_height="80px",
                ),
                rx.cond(
                    LiveState.close_error != "",
                    rx.callout(LiveState.close_error, color_scheme="red", size="1"),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            on_click=LiveState.cancel_close,
                        ),
                    ),
                    rx.button(
                        "Close now", color_scheme="red", on_click=LiveState.confirm_close
                    ),
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
        open=LiveState.show_close_dialog,
    )


def live_page():
    return container(
        navbar(),
        rx.vstack(
            rx.hstack(
                rx.heading("Live Q&A", size="6"),
                rx.spacer(),
                rx.button(
                    "+ New room",
                    on_click=LiveState.open_create,
                    size="2",
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                "Rooms you've asked. Answers stay private until the question "
                "closes — then this page links the permanent results.",
                size="2",
            ),
            rx.cond(
                LiveState.rows.length() == 0,
                rx.callout(
                    "You haven't asked any live questions yet. Create a room "
                    "and share the QR code with your audience.",
                    size="1",
                ),
                rx.fragment(),
            ),
            rx.foreach(
                LiveState.rows,
                lambda r: _room_row(r, LiveState),
            ),
            _create_dialog(),
            _close_note_dialog(),
            spacing="4",
            align="stretch",
            width="100%",
            padding="24px",
        ),
    )


@rx.page(route="/live", on_load=LiveState.on_load, **page_params)
def live():
    """Facilitator dashboard for live Q&A rooms."""
    return live_page()


def _admin_row(r: dict) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    rx.cond(r["is_open"], "Live", "Closed"),
                    color_scheme=rx.cond(r["is_open"], "green", "gray"),
                    variant="soft",
                ),
                rx.text(r["answers_text"], size="1", color="#64748b"),
                spacing="2",
                align="center",
            ),
            rx.text(r["question"], size="3", weight="medium"),
            rx.link(r["url"], href=r["url"], size="1"),
            spacing="2",
            align="stretch",
            width="100%",
        ),
        width="100%",
    )


@rx.page(route="/live/all", on_load=LiveAdminState.on_load, **page_params)
def live_all():
    """Admin visibility over every live room."""
    return container(
        navbar(),
        rx.vstack(
            rx.heading("All Live Rooms", size="6"),
            rx.text(
                "Every live Q&A room, including closed artifacts.", size="2"
            ),
            rx.cond(
                LiveAdminState.rows.length() == 0,
                rx.callout("No rooms exist yet.", size="1"),
                rx.fragment(),
            ),
            rx.foreach(
                LiveAdminState.rows,
                _admin_row,
            ),
            spacing="4",
            align="stretch",
            width="100%",
            padding="24px",
        ),
    )
