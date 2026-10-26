"""What a participant experiences when the wifi dies mid-tap.

The unit tests in ``test_room_outbox.py`` cover the arithmetic of the queue.
These cover the thing arithmetic cannot: whether a phone that cannot reach the
server still keeps a participant's words, tells them the truth about it, and
delivers the tap by itself when the signal returns — without ever asking them to
type it again or sending it twice.

Skipped unless ``RHIZ_E2E=1``, because they need:

* the app compiled and running (``reflex run``) at ``RHIZ_BASE``
  (default ``http://localhost:3000``);
* Playwright with a Chromium browser;
* ``DB_URL`` pointing at the *same* database the running app is using, since the
  assertions are made against the rows the browser caused to be written.

    RHIZ_E2E=1 RHIZ_BASE=http://localhost:3000 DB_URL=postgresql://... \
        python -m pytest tests/test_room_offline_e2e.py -q

The outage is simulated by black-holing ``WebSocket.prototype.send`` rather than
by switching the browser offline: Chromium's offline flag leaves an established
socket running, and Reflex keeps writing into a socket whose frames go nowhere —
which is exactly the failure a phone on full bars in a crowded room produces.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
import reflex as rx

pytestmark = pytest.mark.skipif(
    not os.environ.get("RHIZ_E2E"),
    reason="set RHIZ_E2E=1 with a running app at RHIZ_BASE to exercise the browser",
)

BASE = os.environ.get("RHIZ_BASE", "http://localhost:3000")
DB_URL = os.environ.get("DB_URL", "")

# This suite writes rooms and answers and deletes them through the database the
# running app uses. It must not be pointed at a remote database: a mis-set
# DB_URL would make the test browser modify production data.
from urllib.parse import urlparse

_db_host = (urlparse(DB_URL).hostname or "").lower()
_IS_LOCAL = _db_host.startswith("localhost") or _db_host.startswith("127.0.0.1")

if os.environ.get("RHIZ_E2E") and not _IS_LOCAL:
    pytest.skip(
        "RHIZ_E2E requires DB_URL on localhost/127.0.0.1; refusing to run "
        "destructive browser tests against a remote database",
        allow_module_level=True,
    )


# --------------------------------------------------------------------------
# reaching the database the browser is writing to
# --------------------------------------------------------------------------
def sql(query, params=()):
    import psycopg2

    with psycopg2.connect(DB_URL) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()


def answer_count(slug, content):
    return sql(
        """select count(*) from reckoning r join "group" g on g.id = r.group_id
           where g.slug = %s and r.content = %s and r.removed_at is null""",
        (slug, content),
    )[0][0]


def swap_count(slug):
    return sql(
        """select count(*) from roomswap s join "group" g on g.id = s.room_id
           where g.slug = %s""",
        (slug,),
    )[0][0]


def answer_id(slug, content):
    rows = sql(
        """select r.id from reckoning r join "group" g on g.id = r.group_id
           where g.slug = %s and r.content = %s""",
        (slug, content),
    )
    return rows[0][0] if rows else None


def wait_for(predicate, seconds=45):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.7)
    return predicate()


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def browser_session():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture()
def room_slug():
    """A room of one's own, so counts never bleed between scenarios."""
    from datetime import datetime, timezone

    from sqlmodel import select

    from rhiz.state.base import User
    from rhiz.utils.rooms import create_room
    from rhiz.utils.security import hash_password

    with rx.session() as session:
        host = session.exec(
            select(User).where(User.username == "e2e-outbox-host")
        ).first()
        if host is None:
            host = User(
                username="e2e-outbox-host",
                email="e2e-outbox-host@test.local",
                password=hash_password("Test_pass123"),
                enabled=True,
                role=0,
                can_create_groups=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(host)
            session.commit()
            session.refresh(host)
        room = create_room(session, "E2E outbox question", host.id, 240)
        return room.slug


@pytest.fixture()
def device(browser_session, room_slug):
    """One participant = one browser context = one device identity."""
    from types import SimpleNamespace

    errors: list[str] = []
    page = browser_session.new_context().new_page()
    # The hydration mismatch on every page is a pre-existing app-shell defect
    # (rx.html meta tags render as <div> inside <head>); it says nothing about
    # the outbox and would drown real errors here.
    page.on(
        "pageerror",
        lambda exc: errors.append(str(exc)) if "Hydration" not in str(exc) else None,
    )
    page.goto(f"{BASE}/room/{room_slug}/", wait_until="networkidle")
    page.wait_for_selector("#rhiz-answer", timeout=30000)
    yield SimpleNamespace(page=page, slug=room_slug, errors=errors)
    page.context.close()


def uplink_fails(page):
    """Stop frames leaving while the socket still looks open."""
    page.evaluate(
        """() => { window.__realSend = WebSocket.prototype.send;
                   WebSocket.prototype.send = function () {}; }"""
    )
    page.wait_for_timeout(600)


def uplink_returns(page):
    page.evaluate("() => { WebSocket.prototype.send = window.__realSend; }")
    page.wait_for_timeout(1500)


def queued(page, slug, kind):
    import json

    blob = page.evaluate("() => localStorage.getItem('rhiz_room_outbox_v2') || '{}'")
    return json.loads(blob).get(slug, {}).get(kind)


def banner_shown(page):
    """Is the 'waiting to send' notice actually on screen?

    Its wording is always present in the DOM — the page renders
    '{count} waiting to send' and the helper shows or hides it — so the text
    cannot say whether a participant is being told anything.
    """
    return page.evaluate(
        """() => { const el = document.getElementById('rhiz-outbox-note');
                   return !!el && getComputedStyle(el).display !== 'none'; }"""
    )


# --------------------------------------------------------------------------
# scenarios
# --------------------------------------------------------------------------
def test_a_answer_sent_on_a_working_connection_reaches_the_server(device, room_slug):
    """Baseline: the outbox must not interfere with a healthy tap."""
    text = f"A baseline answer [{uuid.uuid4().hex[:6]}]"
    device.page.fill("#rhiz-answer", text)
    device.page.click("#rhiz-submit-answer")
    assert wait_for(lambda: answer_count(room_slug, text) == 1), (
        "a submit with a working connection did not create the answer"
    )
    assert not queued(device.page, device.slug, "answer"), "a delivered answer stayed queued"
    assert not device.errors, device.errors[:2]


def test_a_tap_made_offline_is_held_on_the_device(device, room_slug):
    text = f"An answer typed while the wifi was down [{uuid.uuid4().hex[:6]}]"
    uplink_fails(device.page)
    device.page.fill("#rhiz-answer", text)
    device.page.click("#rhiz-submit-answer")
    device.page.wait_for_timeout(1500)

    assert (queued(device.page, device.slug, "answer") or {}).get("text") == text, (
        "the tap was not recorded on the device"
    )
    assert banner_shown(device.page), (
        "the page did not say the answer is waiting to send"
    )
    assert answer_count(room_slug, text) == 0, (
        "something reached the server despite the uplink being dead"
    )


def test_a_typed_answer_survives_a_reload_without_being_sent(device, room_slug):
    """Reloading the room page must not silently turn typing into a send."""
    text = f"Words typed but never chosen to send [{uuid.uuid4().hex[:6]}]"
    device.page.fill("#rhiz-answer", text)
    device.page.wait_for_timeout(1200)
    device.page.reload(wait_until="networkidle")
    device.page.wait_for_selector("#rhiz-answer", timeout=30000)

    # The helper refills the field just after the page mounts; give it that
    # moment — a participant staring at a blank box for a second is one thing,
    # a blank box that stays blank is the bug.
    assert wait_for(
        lambda: device.page.input_value("#rhiz-answer") == text, 10
    ), "a reload threw away what the participant had typed"
    assert answer_count(room_slug, text) == 0, (
        "a reload submitted an answer the participant never submitted"
    )
    assert not banner_shown(device.page), (
        "the banner claimed a send that was never tapped"
    )


def test_a_queued_answer_is_delivered_by_itself_when_the_uplink_returns(
    device, room_slug
):
    text = f"An answer that waits for the signal [{uuid.uuid4().hex[:6]}]"
    uplink_fails(device.page)
    device.page.fill("#rhiz-answer", text)
    device.page.click("#rhiz-submit-answer")
    device.page.wait_for_timeout(1200)
    assert queued(device.page, device.slug, "answer"), "nothing was queued to deliver later"

    uplink_returns(device.page)
    assert wait_for(lambda: answer_count(room_slug, text) == 1), (
        "the queued answer was not delivered on its own"
    )
    assert not queued(device.page, device.slug, "answer"), "the device kept a delivered answer"
    assert wait_for(lambda: not banner_shown(device.page)), (
        "the banner still claims work that is already done"
    )
    assert not device.errors, device.errors[:2]  # type: ignore[attr-defined]


def test_replaying_a_delivered_answer_does_not_post_it_twice(device, room_slug):
    """The reply can be lost even though the write landed; replay must be safe."""
    text = f"An answer whose reply was lost [{uuid.uuid4().hex[:6]}]"
    uplink_fails(device.page)
    device.page.fill("#rhiz-answer", text)
    device.page.click("#rhiz-submit-answer")
    device.page.wait_for_timeout(1000)
    uplink_returns(device.page)
    assert wait_for(lambda: answer_count(room_slug, text) == 1)

    # Stand in for a device that never saw the acknowledgement.
    device.page.evaluate(
        """(args) => localStorage.setItem('rhiz_room_outbox_v2', JSON.stringify(
            {[args.slug]: {answer: {text: args.text, at: Date.now()}}}))""",
        {"slug": room_slug, "text": text},
    )
    device.page.evaluate("window.rhizOutboxPaint && window.rhizOutboxPaint()")
    device.page.evaluate("document.getElementById('rhiz-outbox-send')?.click()")
    assert wait_for(lambda: not queued(device.page, device.slug, "answer"), 30), (
        "the replay did not drain"
    )
    assert answer_count(room_slug, text) == 1, "a replay posted a second answer"


def test_a_support_tap_made_offline_becomes_a_vote_when_the_signal_returns(
    browser_session, room_slug
):
    """The vote is the write that matters most; losing it silently is worst.

    Device one answers. Device two types something near-identical, is nudged with
    'someone said this already', and taps *Support this* with the uplink dead.
    """
    import uuid as _uuid

    tag = _uuid.uuid4().hex[:6]
    theirs = f"People spend far too long in status meetings [{tag}]"
    mine = f"People spend far too long in status meetings, sadly [{tag}]"

    first = browser_session.new_context().new_page()
    first.goto(f"{BASE}/room/{room_slug}/", wait_until="networkidle")
    first.wait_for_selector("#rhiz-answer", timeout=30000)
    first.fill("#rhiz-answer", theirs)
    first.click("#rhiz-submit-answer")
    assert wait_for(lambda: answer_id(room_slug, theirs) is not None), (
        "the first device's answer never landed"
    )
    target = answer_id(room_slug, theirs)
    first.context.close()

    second = browser_session.new_context().new_page()
    second.goto(f"{BASE}/room/{room_slug}/", wait_until="networkidle")
    second.wait_for_selector("#rhiz-answer", timeout=30000)
    second.fill("#rhiz-answer", mine)
    second.click("#rhiz-submit-answer")
    assert wait_for(
        lambda: "support that instead" in second.inner_text("body"), 15
    ), "the nudge screen never appeared for a near-identical answer"

    uplink_fails(second)
    second.click(f"#rhiz-support-{target}")
    second.wait_for_timeout(1500)
    assert (queued(second, room_slug, "support") or {}).get("reckoning_id") == target, (
        "the vote was not recorded on the device"
    )
    assert swap_count(room_slug) == 0, "a vote reached the server over a dead uplink"

    uplink_returns(second)
    assert wait_for(lambda: swap_count(room_slug) == 1), (
        "the queued vote was not cast on its own when the signal returned"
    )
    assert not queued(second, room_slug, "support"), (
        "the device kept a vote it had already cast"
    )
    assert "you chose to support" in second.inner_text("body").lower(), (
        "the page never acknowledged the vote that landed"
    )

    # And casting it twice must not move the vote a second time.
    second.evaluate(
        """(args) => localStorage.setItem('rhiz_room_outbox_v2', JSON.stringify(
            {[args.slug]: {support: {reckoning_id: args.id, at: Date.now()}}}))""",
        {"slug": room_slug, "id": target},
    )
    second.evaluate("window.rhizOutboxPaint && window.rhizOutboxPaint()")
    second.evaluate("document.getElementById('rhiz-outbox-send')?.click()")
    assert wait_for(lambda: not queued(second, room_slug, "support"), 30), (
        "replay never drained"
    )
    assert swap_count(room_slug) == 1, "a replayed vote double-counted"
    second.context.close()
