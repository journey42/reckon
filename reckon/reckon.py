"""App routes"""
import reflex as rx
from .pages import home, login, logged_out, about, guidelines, privacy, terms, signup, register, reset_password, reset_password_via_email, request_reset_password, reset_password_email_sent, reset_password_successful, reset_password_via_email_successful, signup_successful, profile, profile_updated, users, log, new_concepts, trending_concepts, your_reckonings, comments, concept, your_drafts, compare
from reckon.styles import reckon_green
from posthog import Posthog

posthog = Posthog(project_api_key='phc_rQPhVDnHM6wgc44Eq3lQayCH4rSOZH3jevGH2B4aFpo', host='https://app.posthog.com')

# posthog.capture('test-id', 'test-event')

app = rx.App(
    theme=rx.theme(
        appearance="light", has_background=True, radius="full", accent_color="gray"
    )
)
