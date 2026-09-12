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

from rhiz.state.base import AppState, Group, GroupStatus, Reckoning, User
from rhiz.utils.rooms import (
    DURATION_CHOICES,
    DEFAULT_DURATION_MINUTES,
    DEFAULT_SIMILARITY_THRESHOLD,
    THRESHOLD_CHOICES,
    close_room,
    create_room,
    delete_room,
    enforce_deadline,
    extend_room,
)
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

    # Delete dialog (per room)
    show_delete_dialog: bool = False
    delete_room_id: int = 0
    delete_room_name: str = ""
    delete_room_open: bool = False
    delete_error: str = ""

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
                        "creator": "",
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
            if room is not None and self._may_manage(room):
                extend_room(session, room_id)
        self._refresh()

    def _may_manage(self, room: Group) -> bool:
        """Facilitators manage their own rooms; admins manage any of them."""
        if self.user is None or not room.is_room:
            return False
        return room.created_by == self.user.id or self.user.role >= 2

    def open_close(self, room_id: int):
        with rx.session() as session:
            room = session.get(Group, room_id)
            if room is None or not self._may_manage(room):
                return
            self.close_room_name = room.founding_question
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
            if room is None or not self._may_manage(room):
                return
            close_room(session, room.id, closing_note=self.close_note_input)
        self.show_close_dialog = False
        self._refresh()

    # ------------------------------------------------------------------
    # Deleting a room
    # ------------------------------------------------------------------

    def open_delete(self, room_id: int):
        with rx.session() as session:
            room = session.get(Group, room_id)
            if room is None or not self._may_manage(room):
                return
            self.delete_room_name = room.founding_question
            self.delete_room_open = room.status == GroupStatus.open
            self.delete_room_id = room_id
        self.delete_error = ""
        self.show_delete_dialog = True

    def cancel_delete(self):
        self.show_delete_dialog = False
        self.delete_room_id = 0
        self.delete_error = ""

    def confirm_delete(self):
        """Permanently delete a room.

        Facilitators delete their own rooms; admins delete any. Room content
        is anonymous and room-scoped, so it is deleted with the room rather
        than surviving as site-wide content (see utils.rooms.delete_room).
        """
        if not self.delete_room_id:
            return
        is_admin = bool(self.user and self.user.role >= 2)
        with rx.session() as session:
            room = session.get(Group, self.delete_room_id)
            if room is None or not room.is_room:
                self.delete_error = "That room no longer exists."
                return
            if not self._may_manage(room):
                self.delete_error = "You can only delete your own rooms."
                return
            delete_room(
                session,
                room.id,
                owner_id=None if is_admin else self.user.id,
                actor_id=self.user.id,
            )
        self.show_delete_dialog = False
        self.delete_room_id = 0
        self._refresh()


class LiveAdminState(LiveState):
    """Admin view: every room, not just mine."""

    def _refresh(self):
        # Keep showing the admin list (every room) after an action.
        self._refresh_all()

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
            # Outer join so each room's creator comes back in one query,
            # matching how the admin Groups page lists its rows.
            pairs = session.exec(
                select(Group, User.username)
                .outerjoin(User, User.id == Group.created_by)
                .where(Group.is_room == True)  # noqa: E712
                .order_by(Group.created_at.desc())
            ).all()
            for room, creator_username in pairs:
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
                        int((room.close_at - datetime.utcnow()).total_seconds()),
                    )
                url = f"{base}/room/{room.slug}"
                self.rows.append(
                    {
                        "id": room.id,
                        "slug": room.slug,
                        "question": room.founding_question,
                        "status": room.status,
                        "is_open": room.status == GroupStatus.open,
                        "answers_text": f"{answers} answers",
                        "remaining_text": (
                            f"closes in ~{remaining // 60} min"
                            if room.status == GroupStatus.open and remaining > 0
                            else ""
                        ),
                        "url": url,
                        "qr": qr_data_uri(url),
                        "is_public": room.is_public,
                        "creator": creator_username or "Unknown",
                    }
                )


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

def _room_row(r: dict, state_cls) -> rx.Component:
    """A single room card.

    Deliberately mirrors :func:`rhiz.pages.group_common.group_row` so the live
    pages read like the Groups pages: a responsive flex (stacked into a column
    on small screens so the buttons stay tappable rather than clipping off the
    right edge), share link + QR on the left, soft action buttons on the right.
    """
    return rx.card(
        rx.flex(
            rx.vstack(
                rx.heading(r["question"], size="3"),
                rx.link(
                    r["url"],
                    href=r["url"],
                    size="1",
                    width="100%",
                    style={"wordBreak": "break-all"},
                ),
                rx.text("Status: ", r["status"], size="1"),
                rx.text(r["answers_text"], size="1", color="gray"),
                rx.cond(
                    r["remaining_text"] != "",
                    rx.text(r["remaining_text"], size="1", color="gray"),
                    rx.fragment(),
                ),
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
            rx.cond(
                r["qr"] != "",
                rx.image(
                    src=r["qr"],
                    width="96px",
                    height="96px",
                    flex_shrink="0",
                ),
                rx.fragment(),
            ),
            rx.vstack(
                rx.cond(
                    r["is_open"],
                    rx.fragment(
                        rx.button(
                            "Extend +15 min",
                            on_click=state_cls.extend(r["id"]),
                            variant="soft",
                            size="1",
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                        rx.button(
                            "Close",
                            on_click=state_cls.open_close(r["id"]),
                            color_scheme="red",
                            variant="soft",
                            size="1",
                            width=rx.breakpoints(initial="100%", sm="auto"),
                        ),
                    ),
                    rx.fragment(),
                ),
                rx.button(
                    "Delete",
                    on_click=state_cls.open_delete(r["id"]),
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


def _close_note_dialog(state_cls) -> rx.Component:
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
                    value=state_cls.close_note_input,
                    on_change=state_cls.set_close_note_input,
                    width="100%",
                    min_height="80px",
                ),
                rx.cond(
                    state_cls.close_error != "",
                    rx.callout(state_cls.close_error, color_scheme="red", size="1"),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            on_click=state_cls.cancel_close,
                        ),
                    ),
                    rx.button(
                        "Close now",
                        color_scheme="red",
                        on_click=state_cls.confirm_close,
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
        open=state_cls.show_close_dialog,
    )


def _delete_dialog(state_cls) -> rx.Component:
    """Confirm permanent deletion of a room and all of its answers."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Delete this room?"),
                rx.cond(
                    state_cls.delete_room_name != "",
                    rx.text(
                        state_cls.delete_room_name,
                        size="3",
                        weight="medium",
                    ),
                    rx.fragment(),
                ),
                rx.callout(
                    "This permanently deletes the room, every anonymous answer, "
                    "and the results page. The link stops working. This cannot "
                    "be undone.",
                    color_scheme="red",
                    variant="soft",
                    size="2",
                ),
                rx.cond(
                    state_cls.delete_room_open,
                    rx.text(
                        "This room is still live — participants will lose their "
                        "answers immediately.",
                        size="2",
                        color="#b91c1c",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    state_cls.delete_error != "",
                    rx.callout(state_cls.delete_error, color_scheme="red", size="1"),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            on_click=state_cls.cancel_delete,
                        ),
                    ),
                    rx.dialog.close(
                        rx.button(
                            "Delete room",
                            color_scheme="red",
                            on_click=state_cls.confirm_delete,
                        ),
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
        open=state_cls.show_delete_dialog,
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
            _close_note_dialog(LiveState),
            _delete_dialog(LiveState),
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


@rx.page(route="/live/all", on_load=LiveAdminState.on_load, **page_params)
def live_all():
    """Admin visibility over every live room."""
    return container(
        navbar(),
        rx.vstack(
            rx.heading("All Live Rooms", size="6"),
            rx.text(
                "Every live Q&A room, including closed artifacts. Close a live "
                "room to freeze it, or delete one to remove it and its "
                "anonymous answers permanently.",
                size="2",
            ),
            rx.cond(
                LiveAdminState.rows.length() == 0,
                rx.callout("No rooms exist yet.", size="1"),
                rx.fragment(),
            ),
            rx.foreach(
                LiveAdminState.rows,
                lambda r: _room_row(r, LiveAdminState),
            ),
            _close_note_dialog(LiveAdminState),
            _delete_dialog(LiveAdminState),
            spacing="4",
            align="stretch",
            width="100%",
            padding="24px",
        ),
    )
