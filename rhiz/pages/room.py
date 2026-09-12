"""Live Q&A room page — /room/<slug>.

A room is a private Group in room mode (is_room=True). This page is
deliberately its own state class (composing the shared utils, not the
5-deep group-page inheritance chain) because the room UX shares nothing
with the group feed by design:

  * Before close, nobody sees answers or results — participants see only
    the question, their own answer, or a private similar-answer nudge.
  * Anonymous participation via the `rhiz_device` cookie; no login needed.
  * When the room closes (deadline or facilitator), the same page becomes
    the permanent artifact: final ranking + swap counts + closing note.

State machine by (device cookie, participation, room status):
  open + no answer       -> question + answer box
  open + answered        -> their answer + edit + waiting note
  just submitted + match -> private similar screen (keep mine / swap)
  swapped                -> waiting note (supporting another answer)
  closed                 -> artifact (final ranked results)
"""

import secrets

import reflex as rx
from sqlmodel import select

from rhiz.state.base import AppState, RoomParticipant
from rhiz.utils.rooms import (
    EXTEND_MINUTES,
    THRESHOLD_CHOICES,
    close_room,
    device_hash_for,
    edit_answer,
    extend_room,
    get_or_create_participant,
    get_room,
    my_answer,
    remove_answer_admin,
    room_results,
    room_status,
    set_threshold,
    submit_answer,
    swap_support,
)
from rhiz.styles import page_params
from rhiz.components import container
from rhiz.pages.group_common import public_base_url


def _is_secure_cookie() -> bool:
    import os

    return os.getenv("PUBLIC_BASE_URL", "http://localhost:3000").startswith("https://")


# Poll cadence for waiting screens: every 20s the page reloads itself. The
# server re-checks the deadline on each load, so a waiting tab turns into
# the artifact within ~20s of the room closing. Deliberately far lighter
# than live-results polling on conference wifi.
AUTO_REFRESH_MS = 20000

# Reload the page after AUTO_REFRESH_MS unless the user is mid-interaction:
# a focused input/textarea (answer box, edit draft), an open dialog, or an
# offline device. Skipping the reload while offline matters — reloading with no
# connection lands the tab on the browser's "site can't be reached" error page,
# which destroys the app and its own retry timer, so the attendee is stuck on a
# chrome error screen instead of recovering when signal returns.
REFRESH_SCRIPT = (
    "(function(){"
    f"var DELAY={AUTO_REFRESH_MS};"
    "function tick(){setTimeout(function(){"
    "var el=document.activeElement;"
    "var busy=(el&&(el.tagName==='TEXTAREA'||el.tagName==='INPUT'))"
    "||document.querySelector('[data-state=\"open\"]');"
    "if(busy||navigator.onLine===false){tick();}else{window.location.reload();}"
    "},DELAY);}"
    "tick();})();"
)


class RoomState(AppState):
    # Anonymous device identity. Long-lived; only a per-room hash is stored.
    device_token: str = rx.Cookie(
        "",
        name="rhiz_device",
        path="/",
        max_age=365 * 24 * 60 * 60,
        same_site="lax",
        secure=_is_secure_cookie(),
    )

    # Facilitator QR for the room (set on load for the facilitator only).
    room_qr: str = ""
    room_url: str = ""

    # True once on_load has hydrated the real state. Until then the page
    # renders a spinner instead of default-state UI — otherwise every
    # auto-refresh would briefly flash the answer form (has_answer
    # defaults to False) even after the participant has answered.
    loaded: bool = False

    # Room
    room_slug: str = ""
    room_question: str = ""
    room_not_found: bool = False
    room_status: str = "open"
    remaining_minutes: int = 0
    remaining_seconds: int = 0
    threshold: float = 0.6

    # Facilitator controls
    is_facilitator: bool = False
    show_close_dialog: bool = False
    closing_note_input: str = ""
    close_error: str = ""

    @rx.var
    def threshold_label(self) -> str:
        """Human label for the room's current similarity threshold."""
        for label, value in THRESHOLD_CHOICES:
            if abs(self.threshold - value) < 0.01:
                return label
        return "Balanced"

    @rx.var
    def swaps_summary(self) -> str:
        n = self.total_swaps
        if n == 0:
            return ""
        unit = "participant" if n == 1 else "participants"
        return f"{n} {unit} switched from their own wording to another answer."

    # Participant (this device)
    has_answer: bool = False
    my_answer_content: str = ""
    my_answer_edited: bool = False
    is_supporting: bool = False
    editing: bool = False
    edit_input: str = ""

    # Submit
    answer_input: str = ""
    error: str = ""

    # Private similar screen (only pre-close view of another answer)
    show_nudge: bool = False
    nudge_similar: list[dict] = []

    # Artifact (closed room)
    results: list[dict] = []
    closing_note: str = ""
    total_swaps: int = 0
    can_remove: bool = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def on_load(self):
        self.room_slug = self.get_path_param("slug", "")
        self.room_not_found = False
        self.loaded = False
        self.error = ""
        self.show_nudge = False
        self.editing = False
        self.show_close_dialog = False

        # Silent hydration: a facilitator opening their own room link should
        # see controls; an anonymous visitor must never be redirected.
        self._hydrate_user()

        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is None:
                self.room_not_found = True
                return
            self.room_question = room.founding_question
            self.is_facilitator = bool(
                self.user and (room.created_by == self.user.id or self.user.role >= 2)
            )
            self.can_remove = bool(self.user and self.user.role >= 2)
            if self.is_facilitator:
                from rhiz.utils.qr import qr_data_uri

                self.room_url = f"{public_base_url()}/room/{room.slug}"
                self.room_qr = qr_data_uri(self.room_url)
            self._load_for_status(session, room)
        self.loaded = True

    def _load_for_status(self, session, room):
        info = room_status(session, room)
        self.room_status = info["status"]
        self.remaining_seconds = info["remaining_seconds"]
        self.remaining_minutes = max(0, info["remaining_seconds"] // 60)
        self.threshold = info["threshold"]
        self.closing_note = info["closing_note"] or ""

        if self.room_status == "closed":
            res = room_results(session, room)
            self.results = res["items"]
            self.total_swaps = res["total_swaps"]
            return

        # Open room: where is this device in the flow?
        if not self.device_token:
            return  # fresh device -> answer box
        participant = self._lookup_participant(session)
        if participant is None:
            return
        if participant.supported_answer_id is not None:
            self.is_supporting = True
            self.has_answer = False
        else:
            answer = my_answer(session, participant)
            if answer is not None:
                self.has_answer = True
                self.my_answer_content = answer.content
                self.my_answer_edited = answer.edited_at is not None

    def _lookup_participant(self, session) -> RoomParticipant | None:
        if not self.device_token:
            return None
        return session.exec(
            select(RoomParticipant).where(
                RoomParticipant.device_hash
                == device_hash_for(self.device_token, self.room_slug)
            )
        ).first()

    def _participant(self, session, room) -> RoomParticipant:
        return get_or_create_participant(session, room, self.device_token)

    # ------------------------------------------------------------------
    # Participant flow
    # ------------------------------------------------------------------

    def set_answer_input(self, value: str):
        self.answer_input = value or ""

    def submit_answer(self):
        self.error = ""
        content = self.answer_input.strip()
        if not content:
            self.error = "Write an answer before submitting."
            return
        if not self.device_token:
            self.device_token = secrets.token_urlsafe(32)
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is None:
                self.room_not_found = True
                return
            participant = get_or_create_participant(session, room, self.device_token)
            try:
                answer, similar = submit_answer(session, room, participant, content)
            except ValueError as e:
                self.error = str(e)
                return
            if answer is None:
                self.error = "Could not save your answer. Please try again."
                return
            self.answer_input = ""
            self.has_answer = True
            self.my_answer_content = answer.content
            self.my_answer_edited = False
            self.nudge_similar = similar
            self.show_nudge = bool(similar)

    def keep_mine(self):
        self.show_nudge = False

    def do_swap(self, reckoning_id: int):
        self.error = ""
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is None:
                return
            participant = get_or_create_participant(session, room, self.device_token)
            if not swap_support(session, room, participant, reckoning_id):
                self.error = "You already chose an answer to support."
                return
        self.show_nudge = False
        self.is_supporting = True
        self.has_answer = False

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def start_edit(self):
        self.editing = True
        self.edit_input = self.my_answer_content
        self.error = ""

    def set_edit_input(self, value: str):
        self.edit_input = value or ""

    def cancel_edit(self):
        self.editing = False
        self.error = ""

    def save_edit(self):
        self.error = ""
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is None:
                return
            participant = self._lookup_participant(session)
            if participant is None:
                self.editing = False
                return
            try:
                updated = edit_answer(session, room, participant, self.edit_input)
            except ValueError as e:
                self.error = str(e)
                return
            if updated is not None:
                self.my_answer_content = updated.content
                self.my_answer_edited = updated.edited_at is not None
        self.editing = False

    # ------------------------------------------------------------------
    # Facilitator controls
    # ------------------------------------------------------------------

    def open_close_dialog(self):
        self.closing_note_input = ""
        self.close_error = ""
        self.show_close_dialog = True

    def cancel_close_dialog(self):
        self.show_close_dialog = False

    def set_closing_note_input(self, value: str):
        self.closing_note_input = value or ""

    def confirm_close(self):
        if not self.is_facilitator:
            return
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is None:
                return
            closed = close_room(session, room.id, closing_note=self.closing_note_input)
            if closed is None:
                self.close_error = "The room is already closed."
                return
        self.show_close_dialog = False
        self._reload()

    def extend_deadline(self):
        if not self.is_facilitator:
            return
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is not None:
                extend_room(session, room.id, EXTEND_MINUTES)
        self._reload()

    def set_room_threshold(self, value: str):
        if not self.is_facilitator:
            return
        try:
            threshold = float(value)
        except (TypeError, ValueError):
            return
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is not None:
                set_threshold(session, room.id, threshold)
        self.threshold = threshold

    def admin_remove_answer(self, reckoning_id: int):
        # Re-check the role server-side instead of trusting the cached var,
        # and scope the delete to this room so a crafted event id cannot touch
        # another room's (or the main site's) content.
        self._hydrate_user()
        if not (self.user and self.user.role >= 2):
            return
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is None:
                return
            remove_answer_admin(session, reckoning_id, room_id=room.id)
        self._reload()

    def _reload(self):
        """Re-read everything for the current room."""
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is not None:
                self._load_for_status(session, room)


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

_PRINT_CSS = """
@media print {
  .no-print { display: none !important; }
  body { background: #fff !important; }
  .artifact { box-shadow: none !important; border: none !important; }
}
"""


def _room_header() -> rx.Component:
    """Minimal header — structurally isolated from site navigation."""
    return rx.hstack(
        rx.text("Rhiz · Live Q&A", size="3", weight="bold"),
        rx.spacer(),
        rx.cond(
            RoomState.room_status == "open",
            rx.badge(
                f"Closes in ~{RoomState.remaining_minutes} min",
                color_scheme="blue",
                variant="soft",
                class_name="no-print",
            ),
            rx.badge("Closed", color_scheme="gray", variant="soft"),
        ),
        width="100%",
        align="center",
        padding="16px 20px",
    )


def _facilitator_controls() -> rx.Component:
    return rx.cond(
        RoomState.is_facilitator & (RoomState.room_status == "open"),
        rx.vstack(
            rx.hstack(
                rx.text("Facilitator controls", size="2", weight="medium"),
                rx.spacer(),
                rx.select(
                    [label for label, _ in THRESHOLD_CHOICES],
                    value=RoomState.threshold_label,
                    on_change=RoomState.set_room_threshold,
                    size="1",
                    class_name="no-print",
                ),
                rx.button(
                    f"Extend +{EXTEND_MINUTES} min",
                    on_click=RoomState.extend_deadline,
                    variant="soft",
                    size="1",
                    class_name="no-print",
                ),
                rx.button(
                    "Close question",
                    on_click=RoomState.open_close_dialog,
                    color_scheme="red",
                    variant="soft",
                    size="1",
                    class_name="no-print",
                ),
                spacing="2",
                align="center",
                wrap="wrap",
            ),
            rx.callout(
                "Answers stay private until you close the question. Throw "
                "the QR on screen — final results appear here for everyone "
                "when it closes.",
                color_scheme="blue",
                variant="soft",
                size="1",
                class_name="no-print",
            ),
            rx.cond(
                RoomState.room_qr != "",
                rx.hstack(
                    rx.vstack(
                        rx.image(
                            src=RoomState.room_qr,
                            width="160px",
                            height="160px",
                            alt="Room QR code",
                            border="1px solid #e2e8f0",
                            border_radius="8px",
                            padding="8px",
                            background="white",
                            flex_shrink="0",
                        ),
                        rx.vstack(
                            rx.text(
                                "Show this QR to your audience",
                                size="2",
                                weight="medium",
                            ),
                            rx.text(
                                RoomState.room_url,
                                size="1",
                                color="#64748b",
                                word_break="break-all",
                            ),
                            spacing="1",
                            width="100%",
                            min_width="0",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    width="100%",
                    class_name="no-print",
                ),
                rx.fragment(),
            ),
            spacing="3",
            align="stretch",
            width="100%",
            padding="12px",
            border="1px solid #e2e8f0",
            border_radius="12px",
            background="#f8fafc",
        ),
        rx.fragment(),
    )


def _nudge_screen() -> rx.Component:
    return rx.cond(
        RoomState.show_nudge,
        rx.vstack(
            rx.text(
                "Someone in the room said something similar. "
                "Would you like to support that instead?",
                size="4",
                weight="medium",
            ),
            rx.foreach(
                RoomState.nudge_similar,
                lambda s: rx.card(
                    rx.flex(
                        rx.text(s["content"], size="2", color="#334155"),
                        rx.button(
                            "Support this",
                            size="1",
                            variant="solid",
                            color_scheme="green",
                            on_click=RoomState.do_swap(s["id"]),
                        ),
                        direction="row",
                        justify="between",
                        align="center",
                        gap="12px",
                        width="100%",
                    ),
                    width="100%",
                ),
            ),
            rx.button(
                "Keep my answer",
                size="2",
                variant="soft",
                on_click=RoomState.keep_mine,
            ),
            spacing="3",
            align="stretch",
            width="100%",
        ),
        rx.fragment(),
    )


def _answer_box() -> rx.Component:
    return rx.vstack(
        rx.text("Answer in your own words", size="2", color="#64748b"),
        rx.text_area(
            value=RoomState.answer_input,
            on_change=RoomState.set_answer_input,
            placeholder="Type your answer…",
            width="100%",
            min_height="110px",
            size="3",
        ),
        rx.cond(
            RoomState.error != "",
            rx.callout(RoomState.error, color_scheme="red", size="1"),
            rx.fragment(),
        ),
        rx.button(
            "Submit answer",
            on_click=RoomState.submit_answer,
            size="3",
            width="100%",
        ),
        spacing="3",
        align="stretch",
        width="100%",
    )


def _waiting_note() -> rx.Component:
    return rx.vstack(
        rx.icon("circle-check", size=32, color="#16a34a"),
        rx.text(
            "Your answer is in. Results appear here automatically when "
            "the question closes.",
            size="3",
            color="#334155",
            text_align="center",
        ),
        rx.text(
            "You can keep the tab open or come back to this link later.",
            size="2",
            color="#64748b",
        ),
        spacing="3",
        align="center",
        width="100%",
        on_mount=rx.call_script(REFRESH_SCRIPT),
    )


def _supporting_note() -> rx.Component:
    return rx.vstack(
        rx.icon("heart-handshake", size=32, color="#16a34a"),
        rx.text(
            "You chose to support another participant's answer.",
            size="3",
            color="#334155",
            text_align="center",
        ),
        rx.text(
            "Final results appear here when the question closes.",
            size="2",
            color="#64748b",
        ),
        spacing="3",
        align="center",
        width="100%",
        on_mount=rx.call_script(REFRESH_SCRIPT),
    )


def _my_answer_view() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.badge("Your answer", color_scheme="blue", variant="soft"),
            spacing="2",
            align="center",
        ),
        rx.cond(
            RoomState.editing,
            rx.vstack(
                rx.text_area(
                    value=RoomState.edit_input,
                    on_change=RoomState.set_edit_input,
                    width="100%",
                    min_height="110px",
                    size="3",
                ),
                rx.hstack(
                    rx.button(
                        "Save", on_click=RoomState.save_edit, size="1"
                    ),
                    rx.button(
                        "Cancel",
                        on_click=RoomState.cancel_edit,
                        variant="soft",
                        color_scheme="gray",
                        size="1",
                    ),
                    spacing="2",
                ),
                rx.cond(
                    RoomState.error != "",
                    rx.callout(RoomState.error, color_scheme="red", size="1"),
                    rx.fragment(),
                ),
                spacing="2",
                align="stretch",
                width="100%",
            ),
            rx.vstack(
                rx.text(RoomState.my_answer_content, size="3", color="#0f172a"),
                rx.hstack(
                    rx.button(
                        "Edit answer",
                        on_click=RoomState.start_edit,
                        variant="soft",
                        size="1",
                        class_name="no-print",
                    ),
                    rx.cond(
                        RoomState.my_answer_edited,
                        rx.text("edited", size="1", color="#64748b"),
                        rx.fragment(),
                    ),
                    spacing="2",
                    align="center",
                ),
                spacing="2",
                align="stretch",
                width="100%",
                on_mount=rx.call_script(REFRESH_SCRIPT),
            ),
        ),
        rx.divider(),
        _waiting_note(),
        spacing="3",
        align="stretch",
        width="100%",
        class_name="no-print",
    )


def _artifact() -> rx.Component:
    return rx.vstack(
        rx.heading("Final results", size="5"),
        rx.cond(
            RoomState.closing_note != "",
            rx.callout(
                rx.vstack(
                    rx.text("Closing note", size="1", weight="bold"),
                    rx.text(RoomState.closing_note, size="2"),
                    spacing="1",
                ),
                color_scheme="blue",
                variant="soft",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.foreach(
            RoomState.results,
            lambda item, rank: _result_item_ranked(item, rank),
        ),
        rx.cond(
            RoomState.total_swaps > 0,
            rx.text(RoomState.swaps_summary, size="2", color="#64748b"),
            rx.fragment(),
        ),
        spacing="3",
        align="stretch",
        width="100%",
        class_name="artifact",
    )


def _result_item_ranked(item: dict, rank: int) -> rx.Component:
    """rx.foreach with index gives 0-based rank."""
    return rx.card(
        rx.flex(
            rx.hstack(
                rx.badge(f"#{rank + 1}", variant="soft"),
                rx.cond(
                    item["removed"],
                    rx.badge("Removed by moderator", color_scheme="gray"),
                    rx.fragment(),
                ),
                rx.spacer(),
                # Post-close moderation: admins can remove an answer from the
                # published artifact. Hidden from print.
                rx.cond(
                    RoomState.can_remove & ~item["removed"],
                    rx.button(
                        "Remove",
                        on_click=RoomState.admin_remove_answer(item["id"]),
                        color_scheme="red",
                        variant="soft",
                        size="1",
                        class_name="no-print",
                    ),
                    rx.fragment(),
                ),
                spacing="2",
                width="100%",
            ),
            rx.cond(
                item["removed"],
                rx.fragment(),
                rx.vstack(
                    rx.text(
                        item["content"],
                        size="3",
                        color="#0f172a",
                        word_break="break-word",
                    ),
                    rx.hstack(
                        rx.text(f"Support: {item['support']}", size="1", color="#475569"),
                        rx.cond(
                            item["has_swaps"],
                            rx.text(item["swaps_text"], size="1", color="#475569"),
                            rx.fragment(),
                        ),
                        rx.cond(
                            item["edited"],
                            rx.text("· edited", size="1", color="#64748b"),
                            rx.fragment(),
                        ),
                        spacing="1",
                        align="center",
                    ),
                    spacing="1",
                    align="start",
                    width="100%",
                ),
            ),
            direction="column",
            spacing="2",
            align="stretch",
            width="100%",
        ),
        width="100%",
    )


def _close_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Close this question"),
                rx.dialog.description(
                    "Answers, edits, and support freeze. Everyone with the "
                    "link sees the final results here, permanently.",
                ),
                rx.text_area(
                    placeholder="Closing note (optional) — a sentence to frame the results",
                    value=RoomState.closing_note_input,
                    on_change=RoomState.set_closing_note_input,
                    width="100%",
                    min_height="80px",
                ),
                rx.cond(
                    RoomState.close_error != "",
                    rx.callout(RoomState.close_error, color_scheme="red", size="1"),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            on_click=RoomState.cancel_close_dialog,
                        ),
                    ),
                    rx.button(
                        "Close question",
                        color_scheme="red",
                        on_click=RoomState.confirm_close,
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
        open=RoomState.show_close_dialog,
    )


def room_page() -> rx.Component:
    return rx.box(
        rx.html(f"<style>{_PRINT_CSS}</style>"),
        container(
            rx.cond(
                RoomState.room_not_found,
                rx.center(
                    rx.vstack(
                        rx.heading("Room not found", size="6"),
                        rx.text("This room link is invalid or has been removed."),
                        spacing="3",
                        align="center",
                    ),
                    min_height="60vh",
                ),
                # Before on_load hydrates, render only a spinner: default
                # state would show the answer form to participants who
                # already answered (and "Closes in ~0 min" in the header).
                rx.cond(
                    RoomState.loaded,
                    rx.vstack(
                        _room_header(),
                        _facilitator_controls(),
                        rx.heading(RoomState.room_question, size="6"),
                        # ---- closed: the artifact ----
                        rx.cond(
                            RoomState.room_status == "closed",
                            _artifact(),
                            # ---- open: participant flow ----
                            rx.vstack(
                                _nudge_screen(),
                                rx.cond(
                                    RoomState.show_nudge,
                                    rx.fragment(),
                                    rx.cond(
                                        RoomState.is_supporting,
                                        rx.vstack(
                                            _supporting_note(),
                                            _facilitator_answer_box(),
                                            spacing="3",
                                            width="100%",
                                        ),
                                        rx.cond(
                                            RoomState.has_answer,
                                            _my_answer_view(),
                                            _answer_box(),
                                        ),
                                    ),
                                ),
                                spacing="4",
                                align="stretch",
                                width="100%",
                            ),
                        ),
                        spacing="4",
                        align="stretch",
                        width="100%",
                    ),
                    rx.center(
                        rx.spinner(size="3"),
                        min_height="50vh",
                        width="100%",
                    ),
                ),
            ),
            _close_dialog(),
            spacing="4",
            align="stretch",
            width="100%",
            padding="0 20px 48px 20px",
        ),
    )


def _facilitator_answer_box() -> rx.Component:
    """A facilitator who hasn't answered can still participate."""
    return rx.cond(
        RoomState.is_facilitator & (RoomState.room_status == "open"),
        rx.cond(
            RoomState.has_answer | RoomState.is_supporting,
            rx.fragment(),
            rx.vstack(
                rx.divider(),
                _answer_box(),
                spacing="3",
                width="100%",
            ),
        ),
        rx.fragment(),
    )


@rx.page(route="/room/[slug]", on_load=RoomState.on_load, **page_params)
def room():
    """Live Q&A room page (anonymous-capable)."""
    return room_page()
