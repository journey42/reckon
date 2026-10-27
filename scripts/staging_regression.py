#!/usr/bin/env python3
"""Regression pass driven against a *deployed* environment (staging).

The suites under tests/ cover the code. This one covers the deployment: the
static config, the baked API host, the DB the app is really talking to, and the
specific bugs the client reported, checked against rows that already exist on
staging (a restore of production) rather than fixtures.

    export RHIZ_BASE=https://mango-tree-0e1baaf0f.eastus2.1.azurestaticapps.net
    export DB_URL=<the dsn that app is connected to>
    export RHIZ_REG_ADMIN_USER=regtest_admin RHIZ_REG_ADMIN_PASSWORD=...
    export RHIZ_REG_USER_USER=regtest_user  RHIZ_REG_USER_PASSWORD=...
    python scripts/staging_regression.py

Run scripts/seed_staging_test_user.py first to create the two accounts.

Refuses to run against production: the pass signs in, opens pages and submits
forms, and a form submitted against production is a real user's action.
"""

from __future__ import annotations

import os
import re
import sys
import time
from urllib.parse import urlparse

import sqlalchemy as sa

BASE = (os.environ.get("RHIZ_BASE") or "").rstrip("/")

# The backend a staging frontend must be wired to. Checked against the socket
# URLs the browser actually opens, because a build baked with the wrong API_URL
# looks identical until someone submits an answer into production.
EXPECTED_API_HOST = os.environ.get("RHIZ_EXPECT_API_HOST", "rhiz-backend-staging")
FORBIDDEN_HOSTS = (
    "rhiz-backend.politefield",  # production backend
    "reckon-backend-preview",  # production backend, revision alias
    "www.rhiz.ai",
    "rhiz.ai",
    "thankful-water-0a4f8900f",  # production static app
)

PROD_BASE_PATTERNS = (re.compile(r"(^|\.)rhiz\.ai$"), re.compile(r"^thankful-water-"))

SHOT_DIR = os.environ.get("RHIZ_REG_SHOTS", "/tmp/staging-regression")
TIMEOUT = int(os.environ.get("RHIZ_REG_TIMEOUT", "60000"))

ADMIN_USER = os.environ.get("RHIZ_REG_ADMIN_USER", "regtest_admin")
ADMIN_PW = os.environ.get("RHIZ_REG_ADMIN_PASSWORD", "")
PLAIN_USER = os.environ.get("RHIZ_REG_USER_USER", "regtest_user")
PLAIN_PW = os.environ.get("RHIZ_REG_USER_PASSWORD", "")
DB_URL = os.environ.get("DB_URL", "")

SKIP_DB = "no DB_URL — DB-backed checks skipped"


# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------
def _guard_base() -> str:
    if not BASE:
        sys.exit("Set RHIZ_BASE to the deployed app's origin.")
    host = (urlparse(BASE).hostname or "").lower()
    if any(p.search(host) for p in PROD_BASE_PATTERNS):
        sys.exit(f"{host} is production; this pass writes. Point it at staging.")
    if urlparse(BASE).scheme != "https" and (urlparse(BASE).hostname or "") not in (
        "localhost",
        "127.0.0.1",
    ):
        sys.exit("RHIZ_BASE must be https:// (except localhost) — the pass exercises cookie auth.")
    return host


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def body(page) -> str:
    return norm(page.inner_text("body"))


def shot(page, name: str) -> str:
    os.makedirs(SHOT_DIR, exist_ok=True)
    path = os.path.join(SHOT_DIR, f"{name}.png")
    try:
        page.screenshot(path=path, full_page=True)
    except Exception:  # a missing screenshot must not mask the failure itself
        return "<screenshot failed>"
    return path


def db():
    return sa.create_engine(DB_URL)


# Server-rendered HTML differing from the client's first render is a known
# smell here (the room and demo pages do it): React throws, throws the server
# markup away and re-renders. Reported rather than failed, because a production
# build minifies the message and the page recovers on its own — but a new code
# showing up here means something else started hydrating badly.
# Reflex renders this into the prerendered shell as a plain console.log (React
# Router's hint about HydrateFallback). It appears on any page served from the
# SPA fallback and is not an error — treating it as one made the pass report
# hydration failures that were only ever that log line.
_PRENDER_HINT = re.compile(r"Hey developer")

# Hydration failures are hard failures now. While the cause was unknown they
# were filtered out of hard_errors; a check below asserts their absence instead.
_HYDRATION = re.compile(r"Hydration failed|Minified React error #(418|422|423|424|425)\b")


def wait_for_text(page, needle: str, seconds: float = 20.0) -> bool:
    """Poll for text instead of snapshotting once.

    The app renders from websocket state: a page can paint its shell, then fill
    in the parts that depend on who you are a beat later. Asserting against the
    first paint makes the pass flaky in exactly the places that matter — the
    admin-only controls.
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        if needle in body(page):
            return True
        page.wait_for_timeout(500)
    return needle in body(page)


def hard_errors(errors: list[str]) -> list[str]:
    return [e for e in errors if not _PRENDER_HINT.search(e)]


def rows(query: str, **params):
    with db().connect() as conn:
        return [tuple(r) for r in conn.execute(sa.text(query), params).fetchall()]
def sign_in(page, username: str, password: str) -> None:
    """Log in and wait for the session to actually take.

    Leaving /login too early races the session cookie and the next page renders
    as a stranger, which would look like an authorisation bug.
    """
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=TIMEOUT)
    page.wait_for_timeout(2000)
    page.fill("input[placeholder='Username']", username)
    page.fill("input[type=password]", password)
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: not url.startswith(f"{BASE}/login"), timeout=TIMEOUT)
    page.wait_for_timeout(1500)


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------
CHECKS: list[tuple[str, str]] = []


def check(title: str):
    def deco(fn):
        CHECKS.append((title, fn.__name__))
        fn._title = title
        return fn

    return deco


def _first_room_path() -> str:
    if not DB_URL:
        return "/live"
    found = rows(
        'SELECT slug FROM "group" WHERE is_room = true AND status = \'open\''
        " ORDER BY id DESC LIMIT 1"
    )
    return f"/room/{found[0][0]}" if found else "/live"


@check("no page logs a hydration failure")
def no_hydration_failures(browser):
    """React #418 fired on every route: Reflex's entry hydrates the whole
    document, whose exported <head> can never match the one React renders, so the
    tree was discarded and rebuilt every visit. client_render_plugin.py makes the
    app mount on the client instead, which is the same work without the error.

    Checked here because nothing else would notice a Reflex upgrade quietly
    restoring the stock entry. Only page errors count: the served shell also logs
    React Router's HydrateFallback hint, which is markup, not a failure.
    """
    offenders: list[str] = []
    for path in ("/login", "/demo", "/group/regression-pass-group", _first_room_path()):
        page = browser.new_context().new_page()
        seen: list[str] = []
        page.on(
            "pageerror",
            lambda exc: seen.append(str(exc)[:110]) if _HYDRATION.search(str(exc)) else None,
        )
        try:
            page.goto(f"{BASE}{path}", wait_until="load", timeout=TIMEOUT)
            page.wait_for_timeout(6000)
            body = " ".join(page.inner_text("body").split())
            if len(body) < 40:
                seen.append(f"rendered nothing at all ({body[:60]!r})")
        finally:
            page.context.close()
        offenders += [f"{path}: {s}" for s in seen]
    assert not offenders, "hydration failed:\n           " + "\n           ".join(offenders)
    return "prerendered and fallback routes both come up clean"


@check("deep links serve the app (staticwebapp.config fallback)")
def deep_link_serves_the_app(browser):
    page = browser.new_context().new_page()
    try:
        resp = page.goto(f"{BASE}/your_concepts", wait_until="networkidle", timeout=TIMEOUT)
        assert resp and resp.status == 200, f"HTTP {getattr(resp, 'status', '?')}"
        text = body(page)
        assert "404" not in text[:200], f"deep link returned the 404 page: {text[:120]!r}"
        assert len(text) > 40, f"page rendered almost nothing: {text[:120]!r}"
    finally:
        page.context.close()


@check("/outbox.js is served (not swallowed by the SPA fallback)")
def outbox_script_is_served(browser):
    ctx = browser.new_context()
    resp = ctx.request.get(f"{BASE}/outbox.js")
    try:
        assert resp.status == 200, f"HTTP {resp.status}"
        text = resp.text()
        assert "rhiz" in text.lower(), "outbox.js came back but does not look like ours"
    finally:
        ctx.close()


@check("the socket goes to the staging backend, never production")
def websocket_goes_to_staging_backend(browser):
    page = browser.new_context().new_page()
    sockets: list[str] = []
    requested: list[str] = []
    page.on("websocket", lambda ws: sockets.append(ws.url))
    page.on("request", lambda r: requested.append(r.url))
    try:
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(4000)
        assert sockets, "the app never opened a websocket — it is not connected to any backend"
        bad = [u for u in sockets if any(h in u for h in FORBIDDEN_HOSTS)]
        assert not bad, f"socket connected to a production backend: {bad}"
        assert any(EXPECTED_API_HOST in u for u in sockets), (
            f"no socket to {EXPECTED_API_HOST!r}; got {sockets}"
        )
        leaking = sorted({urlparse(u).netloc for u in requested if any(h in u for h in FORBIDDEN_HOSTS)})
        assert not leaking, f"the page fetched from production hosts: {leaking}"
    finally:
        page.context.close()


@check("an ordinary account can sign in")
def ordinary_account_signs_in(browser):
    if not (PLAIN_USER and PLAIN_PW):
        raise AssertionError("RHIZ_REG_USER_USER / RHIZ_REG_USER_PASSWORD not set")
    page = browser.new_context().new_page()
    try:
        sign_in(page, PLAIN_USER, PLAIN_PW)
        assert "/login" not in page.url, f"still on the login page: {page.url}"
    finally:
        page.context.close()


@check("an admin account can sign in")
def admin_account_signs_in(browser):
    if not (ADMIN_USER and ADMIN_PW):
        raise AssertionError("RHIZ_REG_ADMIN_USER / RHIZ_REG_ADMIN_PASSWORD not set")
    page = browser.new_context().new_page()
    try:
        sign_in(page, ADMIN_USER, ADMIN_PW)
        assert "/login" not in page.url, f"still on the login page: {page.url}"
    finally:
        page.context.close()


@check("a group page displays its founding question")
def group_page_shows_its_question(browser):
    """The client's report: group pages showed no question at all."""
    if not DB_URL:
        return SKIP_DB
    found = rows(
        "SELECT g.slug, COALESCE(NULLIF(TRIM(g.founding_question),''),"
        " NULLIF(TRIM(r.content),'')) AS q"
        ' FROM "group" g LEFT JOIN reckoning r ON r.id = g.concept_id'
        " WHERE g.is_public = true AND g.status = 'open'"
        "   AND COALESCE(NULLIF(TRIM(g.founding_question),''), NULLIF(TRIM(r.content),'')) IS NOT NULL"
        " ORDER BY g.id DESC LIMIT 3"
    )
    if not found:
        return "no public open group with a question to check"
    page = browser.new_context().new_page()
    try:
        sign_in(page, PLAIN_USER, PLAIN_PW)
        seen = []
        for slug, question in found:
            page.goto(f"{BASE}/group/{slug}", wait_until="networkidle", timeout=TIMEOUT)
            page.wait_for_timeout(2500)
            text = body(page)
            probe = norm(question)[:60]
            assert probe in text, (
                f"/group/{slug} does not show its question. Expected {probe!r}; "
                f"page said: {text[:400]!r}"
            )
            seen.append(slug)
        return ", ".join(seen)
    finally:
        shot(page, "group-question")
        page.context.close()


@check("a group whose wording lives on the concept still shows it")
def group_page_falls_back_to_the_concept(browser):
    """The #11653 shape: column empty, text only on the founding concept."""
    if not DB_URL:
        return SKIP_DB
    found = rows(
        "SELECT g.slug, TRIM(r.content) FROM \"group\" g"
        " JOIN reckoning r ON r.id = g.concept_id"
        " WHERE g.is_public = true AND TRIM(COALESCE(g.founding_question,'')) = ''"
        "   AND TRIM(COALESCE(r.content,'')) <> '' LIMIT 3"
    )
    if not found:
        return "no rows left in that shape (backfill has run, or there were none)"
    page = browser.new_context().new_page()
    try:
        sign_in(page, PLAIN_USER, PLAIN_PW)
        for slug, question in found:
            page.goto(f"{BASE}/group/{slug}", wait_until="networkidle", timeout=TIMEOUT)
            page.wait_for_timeout(2500)
            text = body(page)
            assert norm(question)[:60] in text, (
                f"/group/{slug} lost the question that only exists on the concept"
            )
        return f"{len(found)} legacy row(s) render correctly"
    finally:
        shot(page, "group-fallback")
        page.context.close()


@check("a live room opens, shows its question, throws no page errors")
def room_page_loads(browser):
    if not DB_URL:
        return SKIP_DB
    found = rows(
        'SELECT g.slug, COALESCE(NULLIF(TRIM(g.founding_question),\'\'),\'\'),'
        '        (u.username = :n) AS mine'
        ' FROM "group" g LEFT JOIN "user" u ON u.id = g.created_by'
        " WHERE g.is_room = true AND g.status = 'open'"
        "   AND (g.close_at IS NULL OR g.close_at > (now() at time zone 'utc'))"
        " ORDER BY mine DESC NULLS LAST, g.id DESC LIMIT 1",
        n=ADMIN_USER,
    )
    if not found:
        return "no open room on this database"
    slug, question, _mine = found[0]
    page = browser.new_context().new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        sign_in(page, PLAIN_USER, PLAIN_PW)
        page.goto(f"{BASE}/room/{slug}", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(3000)
        text = body(page)
        assert len(text) > 40, f"/room/{slug} rendered nothing: {text[:200]!r}"
        if question:
            assert norm(question)[:60] in text, f"/room/{slug} is missing its question"
        hard = hard_errors(errors)
        assert not hard, f"/room/{slug} threw: {hard[:2]}"
    finally:
        shot(page, f"room-{slug}")
        page.context.close()


@check("permanent questions offer no Extend; timed ones do")
def extend_button_matches_the_timer(browser):
    if not DB_URL:
        return SKIP_DB
    permanent = rows(
        'SELECT g.slug FROM "group" g JOIN "user" u ON u.id = g.created_by'
        " WHERE u.username = :n AND g.is_room = true AND g.status = 'open'"
        "   AND g.close_at IS NULL LIMIT 1",
        n=ADMIN_USER,
    )
    timed = rows(
        'SELECT g.slug FROM "group" g JOIN "user" u ON u.id = g.created_by'
        " WHERE u.username = :n AND g.is_room = true AND g.status = 'open'"
        "   AND g.close_at > (now() at time zone 'utc') LIMIT 1",
        n=ADMIN_USER,
    )
    if not permanent or not timed:
        # Half of this check is about the contrast, so passing with one kind
        # missing would assert nothing. Timed fixtures expire, which is exactly
        # how this goes quiet without anyone noticing.
        missing = " and ".join(
            label for label, found in (("permanent", permanent), ("timed", timed)) if not found
        )
        return (
            f"{ADMIN_USER} has no open {missing} question — re-run "
            "scripts/seed_staging_test_user.py (timed fixtures expire)"
        )
    page = browser.new_context().new_page()
    try:
        sign_in(page, ADMIN_USER, ADMIN_PW)
        notes = []
        for label, sets, want in (("permanent", permanent, False), ("timed", timed, True)):
            for (slug,) in sets:
                page.goto(f"{BASE}/room/{slug}", wait_until="networkidle", timeout=TIMEOUT)
                page.wait_for_timeout(3000)
                text = body(page)
                has_extend = "Extend +" in text
                if want:
                    assert has_extend, f"timed question {slug} lost its Extend control"
                else:
                    assert not has_extend, (
                        f"permanent question {slug} offers Extend; extending a question "
                        "with no deadline silently starts a timer"
                    )
                notes.append(f"{label}:{slug}")
        return ", ".join(notes) or "nothing to inspect"
    finally:
        shot(page, "extend-controls")
        page.context.close()


@check("the global question control is admin-only")
def demo_control_visibility(browser):
    page = browser.new_context().new_page()
    try:
        sign_in(page, ADMIN_USER, ADMIN_PW)
        page.goto(f"{BASE}/live", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_selector("text=Live Q&A", timeout=TIMEOUT)
        assert wait_for_text(page, "Demo page (/demo)"), (
            "admin does not see the demo control on /live"
        )
    finally:
        page.context.close()

    page = browser.new_context().new_page()
    try:
        sign_in(page, PLAIN_USER, PLAIN_PW)
        page.goto(f"{BASE}/live", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_selector("text=Live Q&A", timeout=TIMEOUT)
        # Give the admin-only state a chance to arrive before concluding it is
        # absent, or this check would pass for the wrong reason.
        page.wait_for_timeout(6000)
        assert "Demo page (/demo)" not in body(page), "an ordinary user was shown the demo control"
        assert "rhiz-demo-question-select" not in page.content()
    finally:
        shot(page, "demo-visibility")
        page.context.close()


@check("a wrong password is refused, and says so")
def wrong_password_is_refused(browser):
    """The rejection is a browser alert (rx.window_alert), so nothing appears in
    the page body — capture the dialog or the check proves nothing either way.

    This matters because it is the one place a visitor learns their credentials
    were wrong rather than that the app is broken.
    """
    if not (PLAIN_USER and PLAIN_PW):
        raise AssertionError("RHIZ_REG_USER_USER / RHIZ_REG_USER_PASSWORD not set")
    page = browser.new_context().new_page()
    dialogs: list[str] = []

    def on_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", on_dialog)
    try:
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(3000)
        page.fill("input[placeholder='Username']", PLAIN_USER)
        page.fill("input[type=password]", PLAIN_PW + "-definitely-wrong")
        page.click("button[type=submit]")
        deadline = time.time() + 25
        while time.time() < deadline and not dialogs:
            page.wait_for_timeout(500)
        assert dialogs, "no rejection was shown for a wrong password"
        assert "/login" in page.url, f"logged in with a wrong password! {page.url}"
        return dialogs[0][:80]
    finally:
        page.context.close()


@check("/demo renders and answers")
def demo_page_renders(browser):
    page = browser.new_context().new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        resp = page.goto(f"{BASE}/demo", wait_until="networkidle", timeout=TIMEOUT)
        assert resp and resp.status == 200, f"HTTP {getattr(resp, 'status', '?')}"
        page.wait_for_timeout(3000)
        hard = hard_errors(errors)
        assert not hard, f"/demo threw: {hard[:2]}"
        assert len(body(page)) > 40, "/demo rendered nothing"
    finally:
        shot(page, "demo")
        page.context.close()


@check("/resend_verification offers the form and is honest")
def resend_verification_page(browser):
    page = browser.new_context().new_page()
    try:
        page.goto(f"{BASE}/resend_verification", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(2000)
        page.fill("input[placeholder='Username']", "nobody-at-all")
        page.click("button:has-text('Send verification link')")
        page.wait_for_timeout(4000)
        text = body(page)
        assert "exist" not in text.lower(), (
            f"the form reveals whether an account exists: {text[:200]!r}"
        )
    finally:
        shot(page, "resend")
        page.context.close()


@check("/signup and /request_reset_password render")
def public_forms_render(browser):
    page = browser.new_context().new_page()
    try:
        for path in ("/signup", "/request_reset_password"):
            resp = page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=TIMEOUT)
            assert resp and resp.status == 200, f"{path} -> HTTP {getattr(resp, 'status', '?')}"
            page.wait_for_timeout(1500)
            assert len(body(page)) > 40, f"{path} rendered nothing"
    finally:
        page.context.close()


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------
def main() -> int:
    host = _guard_base()
    if not DB_URL:
        print("note: DB_URL is unset — the DB-backed checks will report as skipped.\n")

    from playwright.sync_api import sync_playwright

    names = {fn.__name__: fn for fn in globals().values() if callable(fn)}
    results: list[tuple[str, str, str]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for title, fname in CHECKS:
            fn = names[fname]
            print(f"→ {title}", flush=True)
            try:
                note = fn(browser)
                results.append((title, "pass", note or ""))
            except AssertionError as exc:
                results.append((title, "FAIL", str(exc)))
            except Exception as exc:  # noqa: BLE001 — report, do not crash the pass
                results.append((title, "ERROR", f"{type(exc).__name__}: {exc}"))
        browser.close()

    print(f"\n=== {host} ===")
    failed = 0
    for title, status, note in results:
        if status != "pass":
            failed += 1
        print(f"  [{status:4}] {title}" + (f"\n         {note[:400]}" if note else ""))
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    if failed:
        print(f"screenshots: {SHOT_DIR}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
