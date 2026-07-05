"""Email-verification landing page (/verify_email/[token]).

Consumes the token, enables the account, and redirects to login (carrying the
group `next` so the user lands back on the group after logging in). Public —
no login required.
"""

import reflex as rx

from rhiz.state.base import AppState
from rhiz.utils.verification import verify_and_enable
from rhiz.utils.urls import safe_next_path
from rhiz.components.container import container
from rhiz.styles import page_params


class VerifyEmailState(AppState):
    invalid: bool = False

    def on_load(self):
        """Verify the token (no login required). Redirect to login on success."""
        self.invalid = False
        token = self.get_path_param("token", "")
        nxt = self.router.url.query_parameters.get("next")  # type: ignore[attr-defined]
        with rx.session() as session:
            user = verify_and_enable(session, token)
        if user is None:
            self.invalid = True
            return
        safe = safe_next_path(nxt)
        return rx.redirect(f"/login?next={safe}" if safe else "/login")


def verify_email_page():
    return container(
        rx.center(
            rx.cond(
                VerifyEmailState.invalid,
                rx.vstack(
                    rx.heading("Link invalid or expired", size="6"),
                    rx.text(
                        "This verification link is no longer valid. Try signing "
                        "up again from the group page.",
                        size="3",
                    ),
                    rx.link("Go to login", href="/login"),
                    spacing="3",
                    align="center",
                ),
                rx.text("Verifying your account…", size="3"),
            ),
            min_height="60vh",
        ),
    )


@rx.page(route="/verify_email/[token]", on_load=VerifyEmailState.on_load, **page_params)
def verify_email():
    return verify_email_page()
