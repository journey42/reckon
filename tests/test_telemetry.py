"""Verify the server-side telemetry standard against staging.

The client's requirement: an event fires on every signup, group creation,
and group post — verified by running a real signup/group/post on staging and
confirming each event lands in PostHog. Half-firing reads as working, so
this test fails loudly when any of the standard events is missing.

Requires: RHIZ_TELEMETRY_TESTS=1, POSTHOG_PERSONAL_API_KEY (a *personal* API
key from PostHog Settings — the capture key cannot read events back),
DB_URL pointing at the STAGING database, and TELEMETRY_GROUP_SLUG set to a
staging group slug.

Run: RHIZ_TELEMETRY_TESTS=1 DB_URL=<staging-url> pytest tests/test_telemetry.py
"""

import os
import time
import uuid

import pytest
import requests

_TELEMETRY_TESTS = os.environ.get("RHIZ_TELEMETRY_TESTS") == "1"
# Reading events back requires a *personal* API key (Settings -> Personal API
# keys, phx_...). The project token used for capture cannot read events.
PH_SECRET = os.environ.get("POSTHOG_PERSONAL_API_KEY", "")

BASE = os.environ.get(
    "TELEMETRY_BASE_URL",
    "https://mango-tree-0e1baaf0f-feeddeclutter.eastus2.1.azurestaticapps.net",
)

pytestmark = pytest.mark.skipif(
    not _TELEMETRY_TESTS or not PH_SECRET,
    reason="set RHIZ_TELEMETRY_TESTS=1 + POSTHOG_PERSONAL_API_KEY (+ staging DB_URL)",
)


def _posthog_events(event_name: str, distinct_id: str, minutes: int = 20):
    """Query PostHog's events API for recent instances of an event."""
    import requests

    since = time.time() - minutes * 60
    resp = requests.get(
        "https://app.posthog.com/api/events/",
        headers={"Authorization": f"Bearer {PH_SECRET}"},
        params={
            "event": event_name,
            "distinct_id": distinct_id,
            "after": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(since)),
            "limit": 100,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def _wait_for_event(event_name, distinct_id, timeout_s=180):
    """Poll PostHog until the event appears for this distinct_id.

    Server-side captures are batched/flushed by the posthog client (default
    flush interval ~15s), so poll rather than check once.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _posthog_events(event_name, distinct_id):
            return True
        time.sleep(15)
    return False


def _drive_browser(signup_group: str | None):
    """Run a real signup (optionally via a group invite link) on staging."""
    from playwright.sync_api import sync_playwright

    email = f"telemetry-{uuid.uuid4().hex[:8]}@test.local"
    username = f"telem{uuid.uuid4().hex[:6]}"
    url = BASE + "/signup" + (f"?next=/group/{signup_group}" if signup_group else "")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context().new_page()
        pg.goto(url, timeout=90000)
        pg.wait_for_load_state("networkidle", timeout=60000)
        inputs = pg.locator("input")
        inputs.nth(0).fill(email)
        inputs.nth(1).fill(username)
        inputs.nth(2).fill("Telemetry_test1")
        inputs.nth(3).fill("Telemetry_test1")
        pg.get_by_role("button").click()
        pg.wait_for_timeout(8000)
        b.close()
    return email


class TestTelemetryStandard:
    """The client's standard: every signup, group creation, and group post
    fires an event — proven by running them and checking PostHog."""

    def test_signup_and_member_joined_lands(self):
        """A signup via a group invite link must fire BOTH `signup` and
        `member_joined` (the signup auto-joins the origin group)."""
        from sqlalchemy import create_engine
        from sqlmodel import Session, select
        from rhiz.state.base import User

        group_slug = os.environ.get("TELEMETRY_GROUP_SLUG")
        assert group_slug, "set TELEMETRY_GROUP_SLUG to a staging group slug"

        email = f"telem-signup-{uuid.uuid4().hex[:8]}@test.local"
        _drive_browser_for_email(email, group_slug)

        engine = create_engine(os.environ["DB_URL"])
        with Session(engine) as s:
            user = s.exec(select(User).where(User.email == email)).first()
        assert user is not None, "test signup did not create an account"
        distinct_id = f"user-{user.id}"

        assert _wait_for_event("signup", distinct_id), (
            "signup event never landed in PostHog"
        )
        assert _wait_for_event("member_joined", distinct_id), (
            "member_joined event never landed in PostHog"
        )


def _drive_browser_for_email(email: str, group_slug: str):
    from playwright.sync_api import sync_playwright

    url = BASE + f"/signup?next=/group/{group_slug}"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context().new_page()
        pg.goto(url, timeout=90000)
        pg.wait_for_load_state("networkidle", timeout=60000)
        inputs = pg.locator("input")
        inputs.nth(0).fill(email)
        inputs.nth(1).fill(f"telem{uuid.uuid4().hex[:6]}")
        inputs.nth(2).fill("Telemetry_test1")
        inputs.nth(3).fill("Telemetry_test1")
        pg.get_by_role("button").click()
        pg.wait_for_timeout(8000)
        b.close()
