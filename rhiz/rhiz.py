"""App routes"""

import os
import reflex as rx
import rhiz.pages
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
posthog_script = (
    rx.script(src="/posthog.js") if os.getenv("POSTHOG_PROJECT_API_KEY") else None
)

head_scripts = [rx.script(src="/scrolling.js")]
if posthog_script is not None:
    head_scripts.append(posthog_script)

app = rx.App(
    head_components=head_scripts,
)
