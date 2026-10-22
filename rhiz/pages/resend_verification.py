"""Resend the account-verification link.

A verification link is the only thing between a group signup and a usable
account, and mail gets lost: the link is opened on a phone and the email never
follows, it sits in spam, or 72 hours pass. Until this page existed the only
way out was to sign up again, which fails because the username is already
taken — so the account was simply stuck, and there was no way to ask for the
email again.
"""

import reflex as rx

from rhiz.layouts import auth_layout
from rhiz.styles import (
    button_style,
    form_box_style,
    info_text_style,
    input_style,
    link_style,
    page_params,
)
from rhiz.state.base import AppState
from rhiz.utils.urls import public_origin
from rhiz.utils.verification import IGNORED, SENT, TOO_SOON, resend_verification_link

# Deliberately vague: this form must not confirm which usernames exist, nor
# whether an account is verified, disabled, or awaiting approval.
SENT_NOTICE = (
    "If that account is waiting on a verification link, a new one is on its way."
)
TOO_SOON_NOTICE = "Too many links were sent recently. Please wait an hour and try again."
FAILED_NOTICE = "We could not send the email right now. Please try again shortly."

_NOTICES = {
    SENT: SENT_NOTICE,
    IGNORED: SENT_NOTICE,
    TOO_SOON: TOO_SOON_NOTICE,
}


class ResendVerificationState(AppState):
    """State for the resend-verification form."""

    username: str = ""
    notice: str = ""

    @rx.event
    def set_username(self, value: str):
        self.username = value or ""

    @rx.event
    def submit(self):
        """Issue a fresh link (the previous one stops working immediately)."""
        self.notice = ""
        username = (self.username or "").strip()
        if not username:
            self.notice = "Enter your username."
            return
        with rx.session() as session:
            outcome = resend_verification_link(
                session, username, base_url=public_origin()
            )
        self.notice = _NOTICES.get(outcome, FAILED_NOTICE)


@rx.page(route="/resend_verification", **page_params)
def resend_verification():
    """The resend-verification page."""
    return auth_layout(
        rx.text(
            "Didn't get your verification email?",
            **info_text_style,
        ),
        rx.text(
            "Enter your username and we'll send a fresh link. The old link "
            "stops working as soon as a new one is sent.",
            size="2",
            color="gray",
        ),
        rx.flex(
            rx.input(
                placeholder="Username",
                on_blur=ResendVerificationState.set_username,
                **input_style,
            ),
            rx.cond(
                ResendVerificationState.notice != "",
                rx.callout(
                    ResendVerificationState.notice,
                    color_scheme="gray",
                    variant="soft",
                    width="100%",
                ),
            ),
            rx.center(
                rx.button(
                    "Send verification link",
                    on_click=ResendVerificationState.submit,
                    **button_style,
                )
            ),
            **form_box_style,
            direction="column",
            spacing="3",
        ),
        rx.text(
            rx.link("Back to login", href="/login", **link_style),
        ),
    )
