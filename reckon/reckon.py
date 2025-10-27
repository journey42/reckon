"""App routes"""

import os
import reflex as rx
from .pages import (
    home,
    login,
    logged_out,
    about,
    guidelines,
    privacy,
    terms,
    signup,
    register,
    reset_password,
    reset_password_via_email,
    request_reset_password,
    reset_password_via_email_request_result,
    reset_password_successful,
    reset_password_via_email_successful,
    signup_successful,
    profile,
    profile_updated,
    users,
    log,
    new_concepts,
    trending_concepts_by_upvotes,
    trending_concepts_by_support,
    your_reckonings,
    comments,
    concept,
    your_drafts,
    compare,
)
from reckon.styles import reckon_green
from posthog import Posthog


def _init_posthog():
    """Initialise PostHog only when explicitly configured."""
    api_key = os.getenv("POSTHOG_PROJECT_API_KEY")
    if not api_key or os.getenv("POSTHOG_DISABLED") == "1":
        return None
    host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")
    return Posthog(project_api_key=api_key, host=host)


posthog = _init_posthog()

# posthog.capture('test-id', 'test-event')
app = rx.App(
    head_components=[
        rx.script(src="/scrolling.js"),
    ],
    theme=rx.theme(
        appearance="light", has_background=True, radius="full", accent_color="gray"
    ),
)
