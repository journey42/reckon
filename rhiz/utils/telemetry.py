"""Centralized PostHog server-side telemetry.

Every server-side capture goes through :func:`capture` so that:

- one place owns the "is telemetry configured" check,
- failures are *logged* instead of silently swallowed (the old
  ``except Exception: pass`` pattern is how events half-fired for weeks
  while looking like they worked — the client's exact complaint),
- event names stay consistent.

Events currently captured server-side:
  signup, login, group_created, member_joined, group_answer_submitted,
  vote_cast, concept_submitted, comment_posted, concept_refreshed,
  content_flagged.
"""

import logging

import os

logger = logging.getLogger("rhiz.telemetry")

# Event names as constants so a typo is a NameError, not a silent no-op.
SIGNUP = "signup"
LOGIN = "login"
GROUP_CREATED = "group_created"
MEMBER_JOINED = "member_joined"
GROUP_ANSWER_SUBMITTED = "group_answer_submitted"
VOTE_CAST = "vote_cast"
CONCEPT_SUBMITTED = "concept_submitted"
COMMENT_POSTED = "comment_posted"
CONCEPT_REFRESHED = "concept_refreshed"
CONTENT_FLAGGED = "content_flagged"


def _client():
    """Return the PostHog client at call time, or None if unconfigured."""
    if os.getenv("POSTHOG_DISABLED") == "1":
        return None
    try:
        from rhiz.rhiz import posthog

        return posthog
    except Exception:  # pragma: no cover - import cycle safety
        return None


def capture(event: str, distinct_id: str | None = None, **props) -> bool:
    """Fire a server-side PostHog event. Returns True if sent.

    Never raises: telemetry failures are logged (visible in container
    logs / Log Analytics) but must not break the user flow they ride on.
    """
    client = _client()
    if client is None:
        # Unconfigured telemetry is a config bug, not a runtime one — make
        # it visible so "half-firing" cannot hide again.
        logger.warning("posthog skip (%s): client not configured", event)
        return False
    try:
        client.capture(
            event,
            distinct_id=distinct_id or "anonymous",
            properties=props or None,
        )
        return True
    except Exception:
        logger.exception("posthog capture failed (%s)", event)
        return False
