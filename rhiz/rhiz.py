"""App routes"""

import os
import reflex as rx
from posthog import Posthog


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
    head_components=head_scripts,
)

import rhiz.pages  # noqa: F401,E402 — registers @rx.page decorated routes
