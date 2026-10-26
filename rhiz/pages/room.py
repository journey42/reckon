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

from rhiz.state.base import AppState, Reckoning, RoomParticipant
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
    reopen_room,
    room_results,
    room_status,
    set_threshold,
    submit_answer,
    swap_support,
)
from rhiz.styles import page_params
from rhiz.components import container
from rhiz.pages.group_common import public_base_url
from rhiz.utils import outbox


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

# ---------------------------------------------------------------------------
# Offline outbox (see assets/outbox.js + rhiz/utils/outbox.py)
#
# A phone in a room of 300 people on one access point cannot ask a server it
# cannot reach to remember anything, so a tap is recorded on the device *first*
# and only then sent. If the send never lands, the intent stays queued and is
# replayed later; the server applies intents as desired state, so replaying one
# cannot double-post.
# ---------------------------------------------------------------------------

# The tap itself is recorded by the browser helper, not by an event defined
# here. A Reflex event handler — `rx.call_script` included — is dispatched *over
# the websocket*, so queueing this way would route the queueing step through the
# very connection that failed. assets/outbox.js watches these button ids on the
# device instead, and needs no server to do it.


# The pending queue travels to the server through an ordinary input binding (see
# _outbox_bridge), because "an event carries the component's value" is Reflex's
# normal, documented path. Depending on what call_script does with a JavaScript
# return value is not: these scripts are therefore side-effect only.

# Hands the server whatever this room is still holding.
OUTBOX_PUSH_SCRIPT = "window.rhizOutboxPush&&window.rhizOutboxPush();"

# On mount: boot the outbox (the asset can arrive after React has mounted, hence
# the guard) and offer anything already queued. With the page's 20s auto-refresh
# this is also the retry heartbeat; the asset adds a faster one of its own.
OUTBOX_MOUNT_SCRIPT = (
    "window.rhizOutboxInit&&window.rhizOutboxInit();" + OUTBOX_PUSH_SCRIPT
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

    # Room QR: shown to everyone while the question is open so participants
    # can share it with neighbors, not just the facilitator on screen.
    room_qr: str = ""
    room_url: str = ""

    # Shareable plain-text summary of the closed room (download/copy).
    artifact_text: str = ""

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
    # "" when the room has no deadline at all — a permanent Q&A (see
    # rhiz.utils.demo) must not advertise "Closes in ~0 min" forever.
    deadline_label: str = ""
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
            from rhiz.utils.qr import qr_data_uri

            self.room_url = f"{public_base_url()}/room/{room.slug}"
            self.room_qr = qr_data_uri(self.room_url)
            self._load_for_status(session, room)
            if self.device_token:
                dhash = device_hash_for(self.device_token, room.slug)
                participant = session.exec(
                    select(RoomParticipant).where(
                        RoomParticipant.device_hash == dhash
                    )
                ).first()
                self.outbox_version = participant.intent_version if participant else 0
            else:
                self.outbox_version = 0
        self.loaded = True

    def _load_for_status(self, session, room):
        info = room_status(session, room)
        self.room_status = info["status"]
        self.remaining_seconds = info["remaining_seconds"]
        self.remaining_minutes = max(0, info["remaining_seconds"] // 60)
        self.deadline_label = (
            "" if info["close_at"] is None else f"Closes in ~{self.remaining_minutes} min"
        )
        self.threshold = info["threshold"]
        self.closing_note = info["closing_note"] or ""

        if self.room_status == "closed":
            res = room_results(session, room)
            self.results = res["items"]
            self.total_swaps = res["total_swaps"]
            self.artifact_text = _artifact_text(room, self.results, self.total_swaps)
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

    # ------------------------------------------------------------------
    # Offline outbox
    # ------------------------------------------------------------------

    # Server-issued revision this device is up to date with. Exposed to the
    # browser so its queue can stamp each intent and the server can reject an
    # older write that a newer one already superseded.
    outbox_version: int = 0

    def flush_outbox(self, payload: str):
        """Apply whatever this device still has queued for this room.

        Reached from the banner button, from the browser's retry timer (it fires
        itself when the connection comes back), and on mount. The payload is
        localStorage contents, so it is untrusted input: it is re-validated and
        re-decided against current state in ``rhiz.utils.outbox``, never executed
        as given.

        The browser's copy is cleared only for what the server has settled
        (applied, already applied, or consciously dropped). Anything that could
        still succeed stays queued for the next round trip.
        """
        intents = outbox.decode_intents(payload)
        carried = bool(payload) and payload.strip() not in ("", "{}", "null")
        if not intents:
            # Entries the server refused to decode or that aged out must still
            # leave the device, or the banner would nag for ever.
            return rx.call_script(outbox.clear_intents_js()) if carried else None

        if not self.room_slug:
            self.room_slug = self.get_path_param("slug", "")
        if not self.device_token:
            # A device that queued its first write while offline has no cookie
            # yet: this round trip is its first contact with the server.
            self.device_token = secrets.token_urlsafe(32)

        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is None:
                # No room to attach the intents to; retrying cannot help.
                return rx.call_script(outbox.clear_intents_js())
            participant = get_or_create_participant(
                session, room, self.device_token
            )
            outcomes = outbox.apply_intents(session, room, participant, intents)
            # Show what just landed, so a replayed answer appears as submitted
            # rather than leaving the form staring back at them. Before
            # hydration there is nothing to update, and on_load renders fresh
            # state moments later anyway.
            if self.loaded:
                # The flags are re-derived, not merely set: this device may well
                # be looking at the nudge screen it just answered, and
                # _load_for_status only ever turns views *on*.
                self.show_nudge = False
                self.has_answer = False
                self.is_supporting = False
                self._load_for_status(session, room)

        waiting = [k for k, outcome in outcomes.items() if outcome == outbox.RETRY]
        self.outbox_version = participant.intent_version or 0
        # Everything that is not still waitable leaves the device — including
        # entries that never decoded, which would otherwise be re-sent on every
        # retry for as long as the tab is open.
        settled = [kind for kind in outbox.KINDS if kind not in waiting]
        if set(settled) & {outbox.KIND_ANSWER, outbox.KIND_EDIT}:
            settled.append("draft")
        return rx.call_script(
            outbox.clear_intents_js(settled, version=self.outbox_version)
        )

    def _answer_settled_js(self):
        """Tell the device its answer is on record, so the queue stops holding
        it (and the banner stops claiming work that is already done).

        Undocumented here deliberately: this Reflex version does not export the
        event-spec type as ``rx.EventSpec``, and annotating a handler's return is
        not worth reaching into framework internals for.
        """
        return rx.call_script(outbox.clear_intents_js([outbox.KIND_ANSWER, "draft"]))

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
            return self._answer_settled_js()

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
        # The device was holding this choice; it is on record now.
        return rx.call_script(outbox.clear_intents_js([outbox.KIND_SUPPORT]))

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
        settled = False
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
                settled = True
        self.editing = False
        if settled:
            # The device was holding this rewording; it is on record now.
            return rx.call_script(
                outbox.clear_intents_js([outbox.KIND_EDIT, "draft"])
            )

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

    def reopen(self):
        """Reopen a closed room for stragglers (facilitator/admin only)."""
        if not self.is_facilitator:
            return
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is not None:
                reopen_room(session, room.id, EXTEND_MINUTES)
        self._reload()

    def publish_answer(self, reckoning_id: int):
        """Publish a room answer to the main site (facilitator/admin only).

        Mirrors the group-concept graduation flow: is_graduated=True keeps
        the answer in the room artifact while surfacing it in site feeds.
        Anonymous submissions publish without an author.
        """
        if not self.is_facilitator:
            return
        with rx.session() as session:
            room = get_room(session, self.room_slug)
            if room is None or room.id is None:
                return
            answer = session.exec(
                select(Reckoning).where(Reckoning.id == reckoning_id)
            ).first()
            if answer is not None and answer.group_id == room.id:
                answer.is_graduated = True
                session.add(answer)
                session.commit()
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
        rx.link(
            rx.text("Rhiz", size="3", weight="bold"),
            href="/",
            is_external=False,
            style={"text_decoration": "none"},
        ),
        rx.text("· Live Q&A", size="3", weight="bold"),
        rx.spacer(),
        rx.cond(
            RoomState.room_status == "open",
            rx.cond(
                RoomState.deadline_label != "",
                rx.badge(
                    RoomState.deadline_label,
                    color_scheme="blue",
                    variant="soft",
                    class_name="no-print",
                ),
                # No deadline: a permanent question, not a room that forgot to
                # close.
                rx.badge(
                    "No timer",
                    color_scheme="teal",
                    variant="soft",
                    class_name="no-print",
                ),
            ),
            rx.badge("Closed", color_scheme="gray", variant="soft"),
        ),
        rx.cond(
            RoomState.is_facilitator & (RoomState.room_status == "closed"),
            rx.button(
                "Reopen question",
                on_click=RoomState.reopen,
                variant="soft",
                size="1",
                class_name="no-print",
            ),
            rx.fragment(),
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
                rx.cond(
                    RoomState.deadline_label != "",
                    rx.button(
                        f"Extend +{EXTEND_MINUTES} min",
                        on_click=RoomState.extend_deadline,
                        variant="soft",
                        size="1",
                        class_name="no-print",
                    ),
                    rx.fragment(),
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
                            # The id carries which wording is being backed; the
                            # browser helper records the tap the moment it
                            # happens. See assets/outbox.js.
                            id=f"rhiz-support-{s['id']}",
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
            id="rhiz-answer",
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
            # Watched by the browser helper, which queues the words on the
            # device before the network is asked to do anything: on conference
            # wifi the tap must not depend on the link being up at that instant.
            id="rhiz-submit-answer",
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
                    id="rhiz-edit",
                    value=RoomState.edit_input,
                    on_change=RoomState.set_edit_input,
                    width="100%",
                    min_height="110px",
                    size="3",
                ),
                rx.hstack(
                    rx.button(
                        "Save",
                        id="rhiz-save-edit",
                        on_click=RoomState.save_edit,
                        size="1",
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


def _participant_qr() -> rx.Component:
    """Compact QR under the question so neighbors can share each other's
    phone links, not just the facilitator's screen projection."""
    return rx.cond(
        RoomState.room_qr != "",
        rx.hstack(
            rx.image(
                src=RoomState.room_qr,
                width="72px",
                height="72px",
                alt="QR code to this question",
                border="1px solid #e2e8f0",
                border_radius="8px",
                padding="4px",
                background="white",
            ),
            rx.vstack(
                rx.text("Share with a neighbor", size="2", weight="medium"),
                rx.text(
                    "Scan to answer from your phone — even sitting side by side.",
                    size="1",
                    color="#64748b",
                ),
                spacing="1",
                width="100%",
                min_width="0",
            ),
            spacing="3",
            align="center",
            width="100%",
            class_name="no-print",
        ),
        rx.fragment(),
    )


def _artifact_text(room, results: list[dict], total_swaps: int) -> str:
    """Build the shareable plain-text summary of a closed room."""
    lines = ["Rhiz · Live Q&A", "", f"Q: {room.founding_question}", ""]
    rank = 0
    for item in results:
        if item.get("removed"):
            lines.append(f"{rank}. [answer removed by moderator]")
        else:
            lines.append(f"{rank}. {item['content']}  ({item['support']} support)")
        rank += 1
    if total_swaps:
        lines.append("")
        lines.append(f"{total_swaps} participants switched to another answer.")
    lines.append("")
    lines.append(f"View online: {public_base_url()}/room/{room.slug}")
    return "\n".join(lines)


def _artifact() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("Final results", size="5"),
            rx.spacer(),
            rx.button(
                "Copy text",
                on_click=rx.set_clipboard(RoomState.artifact_text),
                variant="soft",
                size="1",
                class_name="no-print",
            ),
            rx.button(
                "Download",
                on_click=rx.download(
                    data=RoomState.artifact_text,
                    filename="rhiz-qa-results.txt",
                ),
                variant="soft",
                size="1",
                class_name="no-print",
            ),
            width="100%",
            align="center",
        ),
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
                rx.cond(
                    RoomState.is_facilitator & ~item["removed"] & ~item["graduated"],
                    rx.button(
                        "Publish to site",
                        on_click=RoomState.publish_answer(item["id"]),
                        color_scheme="green",
                        variant="soft",
                        size="1",
                        class_name="no-print",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    item["graduated"],
                    rx.badge("Published", color_scheme="green", size="1"),
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


def _outbox_banner() -> rx.Component:
    """Writes this device is holding because they could not be sent.

    Rendered hidden and revealed by ``assets/outbox.js``: only the browser knows
    whether the device is holding anything, and asking the server is precisely
    what a device with no connection cannot do. The count text is filled by the
    same script, so this markup deliberately carries no numbers to go stale.

    The button doubles as the browser's own retry target, and the hidden field
    beside it is how the queue reaches a state event: both are ordinary Reflex
    behaviour rather than calls into framework internals.
    """
    return rx.box(
        rx.hstack(
            rx.icon("circle-arrow-up", size=16, color="#92400e"),
            rx.text(
                "",
                id="rhiz-outbox-count",
                size="2",
                color="#92400e",
                weight="medium",
            ),
            rx.button(
                "Try now",
                id="rhiz-outbox-send",
                size="1",
                variant="soft",
                color_scheme="amber",
                on_click=rx.call_script(OUTBOX_PUSH_SCRIPT),
            ),
            # The queue's way into a state event: the script writes the pending
            # intents here, and this binding is what turns them into an argument
            # on the server. Invisible, never typed in, and part of the banner so
            # the two are always mounted or hidden together.
            rx.input(
                id="rhiz-outbox-payload",
                on_change=RoomState.flush_outbox,
                tab_index=-1,
                aria_hidden=True,
                pointer_events="none",
                position="absolute",
                width="1px",
                height="1px",
                opacity=0,
                border="none",
                padding=0,
            ),
            # The revision the server has already accepted for this device. The
            # browser stamps each new intent with the next one, so the server
            # can tell a genuinely newer write from a stale replay.
            rx.input(
                id="rhiz-outbox-version",
                value=RoomState.outbox_version.to_string(),
                tab_index=-1,
                aria_hidden=True,
                pointer_events="none",
                position="absolute",
                width="1px",
                height="1px",
                opacity=0,
                border="none",
                padding=0,
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        id="rhiz-outbox-note",
        display="none",
        padding="8px 12px",
        border_radius="8px",
        background="#fef3c7",
        border="1px solid #fde68a",
        width="100%",
        class_name="no-print",
    )


def room_page() -> rx.Component:
    return rx.box(
        rx.html(f"<style>{_PRINT_CSS}</style>"),
        container(
            # Always in the DOM, before hydration: a device that arrives with no
            # signal still has to be able to say "waiting to send".
            _outbox_banner(),
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
                        rx.cond(
                            RoomState.room_status == "open",
                            _participant_qr(),
                            rx.fragment(),
                        ),
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
        # Anything this room is still holding gets offered to the server on every
        # load — which, with the 20s auto-refresh, is also the retry heartbeat.
        on_mount=rx.call_script(OUTBOX_MOUNT_SCRIPT, callback=RoomState.flush_outbox),
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
