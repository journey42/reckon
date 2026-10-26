"""/demo — a permanent Q&A with the explanation printed beside it.

The client wants an address that can go on a business card: somewhere a stranger
arrives, reads two paragraphs about what Rhiz is for, answers immediately, and
finds the answers accumulating underneath rather than expiring.

It is a live Q&A room with no deadline (see ``rhiz.utils.demo``) wearing a
different skin: the same anonymous participant model, the same "someone already
said that — back them instead?" consolidation, the same ranking by support. What
it leaves out is the timer, the QR/share furniture and the facilitator panel,
because someone arriving from a card has no idea what a facilitator is.

Which question is shown is chosen in the admin panel, so it can change between
audiences without a deploy, and every question keeps its own answer history
whether or not it is the one on screen.
"""

from __future__ import annotations

import secrets

import reflex as rx

from rhiz.components import container
from rhiz.state.base import AppState
from rhiz.styles import page_params
from rhiz.utils import demo
from rhiz.utils.rooms import (
    get_or_create_participant,
    my_answer,
    submit_answer,
    swap_support,
)


# The client wrote these two paragraphs and asked for the first above the Q&A
# and the second below it. Rewording them is not ours to do.
EXPLAIN_ABOVE = (
    "Rhiz helps groups discover what they actually believe. When a member posts "
    "a belief, it's compared to everything other members have already submitted. "
    "Similar statements appear ranked by how close they are in meaning, along "
    "with how much support each one has. The member can then stick with their own "
    "wording or back something phrased better or with more traction. Over time, "
    "points of agreement emerge, and the group discovers agreement it didn't know "
    "it had."
)
EXPLAIN_BELOW = (
    "The concept comes from the theory of emergence: complex structures can arise "
    "from small, simple processes. I believe a group has to become legible to "
    "itself before it can become legible to outsiders or to people in power. That "
    "requires individuals to understand the beliefs of the larger group. Right now "
    "my goal is to help groups reach that cohesion. Down the road, I hope Rhiz can "
    "help individuals understand the beliefs of broader society, and help society "
    "better understand itself"
)

DEMO_META = dict(
    page_params,
    title="Rhiz — see what a group actually believes",
    description=(
        "Answer one question and watch the group's actual beliefs rank "
        "themselves. A permanent demonstration of Rhiz."
    ),
)

# Answers arriving while someone reads *is* the demonstration, so the page
# reloads itself on the same cadence the live rooms use. Five things stop it:
# someone typing or holding an unsent draft (never wipe a stranger's words), an
# open dialog, a consolidation offer still on screen (do not pull a decision off
# the screen mid-consideration), answers the reader expanded (a reload would
# collapse them), or a host that cannot be reached (reloading offline hands the
# tab to the browser's error page and destroys the app along with its retry).
DEMO_REFRESH_MS = 20000
DEMO_REFRESH_SCRIPT = (
    "(function(){"
    f"var DELAY={DEMO_REFRESH_MS};"
    "var BOX='rhiz-demo-answer';"
    "var QID='rhiz-demo-question';"
    "function key(){var el=document.getElementById(QID);"
    "var slug=el?el.value:'';return 'rhiz_demo_draft_'+slug+'_v1';}"
    "function draft(){try{return localStorage.getItem(key())||'';}catch(e){return '';}}"
    "function saveDraft(){var el=document.getElementById(BOX);if(!el)return;"
    "try{if(el.value)localStorage.setItem(key(),el.value);else localStorage.removeItem(key());}catch(e){}}"
    "document.addEventListener('input',function(e){"
    "if(e.target&&e.target.id===BOX)saveDraft();},true);"
    # Put unsent typing back after a reload. The field is React-controlled, so
    # dispatching input is what takes the words back into state; it is retried
    # briefly because React can write its own empty value after hydration.
    "function restore(deadline){var el=document.getElementById(BOX);var text=draft();"
    "if(el&&text&&!el.value){el.value=text;"
    "try{el.dispatchEvent(new Event('input',{bubbles:true}));}catch(e){}}"
    "if(Date.now()>=deadline)return;setTimeout(function(){restore(deadline);},300);}"
    "restore(Date.now()+8000);"
    "function busy(){"
    "var el=document.activeElement;"
    "if(el&&(el.tagName==='TEXTAREA'||el.tagName==='INPUT'))return true;"
    "if(document.querySelector('[data-state=\"open\"]'))return true;"
    "if(document.getElementById('rhiz-demo-keep'))return true;"
    # Expanded: reloading would collapse the answers the reader deliberately
    # asked to see more of.
    "if(document.getElementById('rhiz-demo-fewer'))return true;"
    # Unfocused draft: someone typed, then tapped elsewhere. The words are
    # still unsent and a reload would throw them away.
    "if(draft())return true;"
    "return false;}"
    # navigator.onLine says nothing about whether the backend is reachable;
    # a HEAD to our own page catches a dead host before we hand the tab to the
    # browser's error page.
    "function reachable(){return fetch(window.location.href,{method:'HEAD',cache:'no-store'})"
    ".then(function(r){return r.ok;}).catch(function(){return false;});}"
    "function tick(){setTimeout(function(){"
    "if(busy()||navigator.onLine===false){tick();return;}"
    "reachable().then(function(ok){if(ok)window.location.reload();else tick();});"
    "},DELAY);}"
    "tick();"
    "window.rhizDemoClearDraft=function(){try{localStorage.removeItem(key());}catch(e){}};"
    "})();"
)

from rhiz.pages.room import _is_secure_cookie  # noqa: E402  (after styles import)


class DemoState(AppState):
    # The same long-lived device cookie the rooms use: the person who answers
    # here and later walks into a real room is one participant rather than two,
    # and the database still stores only a per-room hash of it.
    device_token: str = rx.Cookie(
        "",
        name="rhiz_device",
        path="/",
        max_age=365 * 24 * 60 * 60,
        same_site="lax",
        secure=_is_secure_cookie(),
    )

    # The question on screen
    # Not `slug`: that name belongs to the dynamic route argument,
    # which Reflex rejects a state var shadowing.
    question_slug: str = ""
    question: str = ""
    not_found: bool = False
    loaded: bool = False

    # Answers, five at a time until asked for more
    answers: list[dict] = []
    total_answers: int = 0
    has_more: bool = False
    expanded: bool = False

    # This device's place in the question
    answer_input: str = ""
    error: str = ""
    has_answer: bool = False
    my_answer_content: str = ""
    is_supporting: bool = False
    show_nudge: bool = False
    nudge_similar: list[dict] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def on_load(self):
        self.not_found = False
        self.error = ""
        self.loaded = False
        self.show_nudge = False
        self.expanded = False
        self.has_answer = False
        self.is_supporting = False
        self.my_answer_content = ""
        # Silent hydration: a signed-in organiser may reach this page and it
        # must never bounce them, but an anonymous visitor stays anonymous.
        self._hydrate_user()

        # Not get_path_param: on a route with no dynamic segment it falls back
        # to the last path segment, which made /demo look like a question whose
        # slug was "demo".
        wanted = (self.router.page.params or {}).get("slug", "")
        with rx.session() as session:
            room = (
                demo.demo_question_by_slug(session, wanted, require_open=True)
                if wanted
                else demo.active_demo_question(session)
            )
            if room is None:
                self.not_found = True
                self.loaded = True
                return
            self.question_slug = room.slug
            self.question = room.founding_question
            self._read_where_i_stand(session, room)
            self._read_answers(session, room)
        self.loaded = True

    def _read_where_i_stand(self, session, room):
        if not self.device_token:
            return
        participant = get_or_create_participant(session, room, self.device_token)
        if participant.supported_answer_id is not None:
            self.is_supporting = True
            return
        answer = my_answer(session, participant)
        if answer is not None:
            self.has_answer = True
            self.my_answer_content = answer.content

    def _read_answers(self, session, room):
        """Five answers, or all of them once they have asked for more."""
        limit = (
            demo.ANSWERS_ABOVE_THE_FOLD
            if not self.expanded
            else max(demo.ANSWERS_ABOVE_THE_FOLD, self.total_answers)
        )
        page = demo.visible_answers(session, room, limit=limit)
        self.answers = page["items"]
        self.total_answers = page["total"]
        self.has_more = page["has_more"]

    def _room(self, session):
        return demo.demo_question_by_slug(
            session, self.question_slug, require_open=True
        )

    # ------------------------------------------------------------------
    # Answering
    # ------------------------------------------------------------------

    def set_answer_input(self, value: str) -> None:
        self.answer_input = value or ""

    def submit(self):
        if not self.question_slug:
            self.error = "There is no question to answer right now."
            return
        self.error = ""
        with rx.session() as session:
            room = self._room(session)
            if room is None:
                self.error = "That question is no longer here."
                return
            if not self.device_token:
                # A first-time visitor has no cookie yet; this write is the
                # moment they become a participant.
                self.device_token = secrets.token_urlsafe(32)
            participant = get_or_create_participant(
                session, room, self.device_token
            )
            try:
                answer, similar = submit_answer(
                    session, room, participant, self.answer_input
                )
            except ValueError as exc:
                self.error = str(exc)
                return
            self.answer_input = ""
            self.has_answer = True
            self.my_answer_content = answer.content if answer else ""
            # Consolidation is the mechanism the explainer above describes, so
            # showing it is the point of the page, not friction in its way.
            self.nudge_similar = similar
            self.show_nudge = bool(similar)
            self.expanded = False
            self._read_answers(session, room)
        return rx.call_script(
            "window.rhizDemoClearDraft&&window.rhizDemoClearDraft();"
        )

    def support(self, reckoning_id: int):
        if not self.question_slug or not self.device_token:
            return
        with rx.session() as session:
            room = self._room(session)
            if room is None:
                return
            participant = get_or_create_participant(
                session, room, self.device_token
            )
            if not swap_support(session, room, participant, reckoning_id):
                self.error = "You already chose an answer to support."
                return
            self.error = ""
            self.show_nudge = False
            self.is_supporting = True
            self.has_answer = False
            self.my_answer_content = ""
            self._read_answers(session, room)

    def keep_mine(self):
        """Close the offer and change nothing.

        The explainer promises a member may keep their own wording; the page has
        to let them do exactly that and get on with reading.
        """
        self.show_nudge = False

    # ------------------------------------------------------------------
    # Reading more, and keeping up
    # ------------------------------------------------------------------

    def show_more(self):
        self.expanded = True
        self._reload_list()

    def show_fewer(self):
        self.expanded = False
        self._reload_list()

    def _reload_list(self):
        if not self.question_slug:
            return
        with rx.session() as session:
            room = self._room(session)
            if room is not None:
                self._read_answers(session, room)

    @rx.var
    def hidden_count(self) -> int:
        return max(0, self.total_answers - demo.ANSWERS_ABOVE_THE_FOLD)

    @rx.var
    def more_label(self) -> str:
        if self.hidden_count <= 0:
            return ""
        unit = "answer" if self.hidden_count == 1 else "answers"
        return f"Show {self.hidden_count} more {unit}"


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
def _top_bar() -> rx.Component:
    """The one thing worth offering someone who arrived from a card."""
    return rx.hstack(
        rx.link(
            rx.text("Rhiz", size="5", weight="bold"),
            href="/",
            is_external=False,
            style={"text_decoration": "none"},
        ),
        rx.spacer(),
        rx.link(
            rx.button("Sign up", size="2", color_scheme="green"),
            href="/signup",
            is_external=False,
        ),
        width="100%",
        align="center",
        padding="14px 0",
    )


def _answer_row(item: dict) -> rx.Component:
    return rx.hstack(
        rx.badge(
            # A Var, not an int: the colour has to be decided server-side
            # (``hot``) and switched with rx.cond, because a page cannot compare
            # an item var with a number at compile time.
            rx.text(item["support"], size="2", weight="bold"),
            color_scheme=rx.cond(item["hot"], "green", "gray"),
            variant="soft",
            min_width="28px",
        ),
        rx.vstack(
            rx.text(item["content"], size="3"),
            rx.cond(
                item["has_swaps"],
                rx.text(
                    f"{item['swaps_text']} · someone changed their wording to this",
                    size="1",
                    color="#64748b",
                ),
                rx.fragment(),
            ),
            align="start",
            spacing="1",
            width="100%",
        ),
        width="100%",
        align="start",
        gap="12px",
        padding="10px 0",
        border_bottom="1px solid var(--gray-a3)",
    )


def _answers() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text("What people have said", size="2", color="#64748b"),
            rx.spacer(),
            rx.cond(
                DemoState.total_answers > 0,
                rx.text(
                    f"{DemoState.total_answers} answers · ranked by support",
                    size="1",
                    color="#94a3b8",
                ),
                rx.fragment(),
            ),
            width="100%",
            align="center",
        ),
        rx.cond(
            DemoState.total_answers > 0,
            rx.vstack(
                rx.foreach(DemoState.answers, _answer_row),
                width="100%",
                spacing="0",
            ),
            rx.text(
                "No answers yet — yours would be the first.",
                size="2",
                color="#94a3b8",
            ),
        ),
        # Two buttons rather than one whose action flips on a condition: the
        # click target stays put, which matters more than saving a component.
        rx.cond(
            DemoState.expanded,
            rx.button(
                "Show fewer answers",
                size="2",
                variant="soft",
                color_scheme="gray",
                on_click=DemoState.show_fewer,
                id="rhiz-demo-fewer",
            ),
            rx.cond(
                DemoState.more_label != "",
                rx.button(
                    DemoState.more_label,
                    size="2",
                    variant="soft",
                    color_scheme="gray",
                    on_click=DemoState.show_more,
                    id="rhiz-demo-more",
                ),
                rx.fragment(),
            ),
        ),
        width="100%",
        align="stretch",
        spacing="3",
    )


def _answer_box() -> rx.Component:
    return rx.vstack(
        rx.text("Your answer", size="2", color="#64748b"),
        rx.text_area(
            id="rhiz-demo-answer",
            value=DemoState.answer_input,
            on_change=DemoState.set_answer_input,
            placeholder="Type your answer…",
            width="100%",
            min_height="100px",
            size="3",
        ),
        rx.cond(
            DemoState.error != "",
            rx.callout(DemoState.error, color_scheme="red", size="1"),
            rx.fragment(),
        ),
        rx.button(
            "Submit answer",
            id="rhiz-demo-submit",
            size="3",
            width="100%",
            on_click=DemoState.submit,
        ),
        width="100%",
        align="stretch",
        spacing="2",
    )


def _my_position() -> rx.Component:
    """What this device has already done, if anything."""
    return rx.cond(
        DemoState.is_supporting,
        rx.callout(
            "You backed someone else's wording. That is counted in the numbers "
            "below.",
            color_scheme="green",
            size="2",
            icon="check",
            width="100%",
        ),
        rx.vstack(
            rx.text("Your answer", size="1", color="#64748b"),
            rx.text(DemoState.my_answer_content, size="3", weight="medium"),
            align="start",
            width="100%",
            padding="10px 12px",
            border_radius="8px",
            background="var(--gray-a2)",
        ),
    )


def _nudge() -> rx.Component:
    """The consolidation offer — the thing this page exists to demonstrate."""
    return rx.cond(
        DemoState.show_nudge,
        rx.vstack(
            rx.text(
                "Someone has already said something similar. Would you like to "
                "support that instead?",
                size="2",
                weight="medium",
            ),
            rx.foreach(
                DemoState.nudge_similar,
                lambda other: rx.hstack(
                    rx.text(other["content"], size="2", color="#334155"),
                    rx.button(
                        "Support this",
                        size="1",
                        variant="solid",
                        color_scheme="green",
                        on_click=DemoState.support(other["id"]),
                    ),
                    width="100%",
                    justify="between",
                    align="center",
                    gap="12px",
                ),
            ),
            rx.button(
                "Keep my wording",
                size="2",
                variant="soft",
                on_click=DemoState.keep_mine,
                # The reload timer looks for this id: while the offer is up,
                # the page must not refresh out from under the decision.
                id="rhiz-demo-keep",
            ),
            width="100%",
            padding="12px",
            border_radius="10px",
            border="1px solid var(--green-6)",
            spacing="3",
            align="stretch",
        ),
        rx.fragment(),
    )


@rx.page(route="/demo", on_load=DemoState.on_load, **DEMO_META)
@rx.page(route="/demo/[slug]", on_load=DemoState.on_load, **DEMO_META)
def demo_page():
    """Permanent Q&A with the client's explanation printed around it."""
    return container(
        rx.vstack(
            _top_bar(),
            rx.input(
                id="rhiz-demo-question",
                value=DemoState.question_slug,
                read_only=True,
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
            rx.cond(
                DemoState.not_found,
                rx.vstack(
                    rx.heading("No question set up yet", size="5"),
                    rx.text(
                        "An organiser needs to add a permanent question before "
                        "this page has anything to ask."
                    ),
                    rx.link("Sign up for Rhiz", href="/signup"),
                    align="start",
                    spacing="3",
                    width="100%",
                    padding="24px 0",
                ),
                rx.vstack(
                    rx.text(
                        EXPLAIN_ABOVE, size="3", color="#334155", line_height="1.7"
                    ),
                    rx.heading(DemoState.question, size="6", margin_top="12px"),
                    rx.cond(
                        DemoState.has_answer | DemoState.is_supporting,
                        _my_position(),
                        _answer_box(),
                    ),
                    _nudge(),
                    _answers(),
                    rx.divider(margin_top="16px"),
                    rx.text(
                        EXPLAIN_BELOW, size="2", color="#64748b", line_height="1.7"
                    ),
                    rx.link("Make your own group →", href="/signup", size="2"),
                    align="stretch",
                    spacing="4",
                    width="100%",
                    padding="16px 0 48px 0",
                ),
            ),
            width="100%",
            max_width="720px",
            padding="0 16px",
            margin="0 auto",
            spacing="3",
            align="stretch",
            on_mount=rx.call_script(DEMO_REFRESH_SCRIPT),
        ),
        max_width="100%",
    )
