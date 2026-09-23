"""App routes"""

import os
import reflex as rx
from posthog import Posthog

from rhiz.utils.unfurl import make_unfurl_app


def _init_posthog():
    """Initialise PostHog only when explicitly configured."""
    api_key = os.getenv("POSTHOG_PROJECT_API_KEY")
    if not api_key or os.getenv("POSTHOG_DISABLED") == "1":
        return None
    host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")
    return Posthog(project_api_key=api_key, host=host)


posthog = _init_posthog() if os.getenv("POSTHOG_SECRET_KEY") else None

# Always include the PostHog client-side script. The API key is hardcoded
# in assets/posthog.js, so we just need the <script> tag to load it.
# This must NOT be gated by an env var, because the env var is only
# available at runtime (not during Docker build / static export).
head_scripts = [
    rx.script(src="/scrolling.js"),
    rx.script(src="/posthog.js"),
]

app = rx.App(
    api_transformer=make_unfurl_app(),
    head_components=[
        # Social unfurl defaults (Discord/X/Slack). Group pages override the
        # description dynamically via their own head_components.
        rx.html('<meta property="og:site_name" content="Rhiz">'),
        rx.html('<meta property="og:title" content="Rhiz — Speak Together">'),
        rx.html(
            '<meta property="og:description" content="Rhiz is a platform for '
            'structured group discussion: propose concepts, support the best '
            'ones, and build understanding together.">'
        ),
        rx.html('<meta property="og:type" content="website">'),
        rx.html('<meta property="og:image" content="/logo.png">'),
        rx.html('<meta name="twitter:card" content="summary">'),
        rx.html(
            '<meta name="description" content="Rhiz is a platform for '
            'structured group discussion: propose concepts, support the best '
            'ones, and build understanding together.">'
        ),
        *head_scripts,
    ],
)

import rhiz.pages  # noqa: F401,E402 — registers @rx.page decorated routes
