"""Navbar component for the app."""

import reflex as rx
from rhiz.components.buttons import (
    legend_button,
    trending_concepts_button,
    your_concepts_button,
    logo_button,
    groups_button,
)
from rhiz.components.feedback_dialog import (
    feedback_dialog,
    FeedbackDialogState,
    general_feedback_options,
)
from rhiz.components.legend_dialog import legend_dialog, LegendDialogState
from rhiz.components.how_it_works_dialog import (
    how_it_works_dialog,
    HowItWorksDialogState,
)
from rhiz.state.base import AppState, UserTypes


def _authenticated_menu_items() -> rx.Component:
    """Dropdown items for a logged-in user."""
    return rx.fragment(
        rx.menu.item(AppState.user.username, disabled=True),
        rx.menu.separator(),
        rx.menu.item("Profile", on_click=rx.redirect("/profile")),
        rx.menu.item("Feedback", on_click=FeedbackDialogState.visible),
        rx.menu.item("How To", on_click=rx.redirect("/how_to")),
        rx.menu.item("Terms", on_click=rx.redirect("/terms")),
        rx.menu.item("Privacy", on_click=rx.redirect("/privacy")),
        rx.cond(
            AppState.user.role == UserTypes.admin,
            rx.menu.separator(),
        ),
        rx.cond(
            AppState.user.role == UserTypes.admin,
            rx.menu.item("Log", on_click=rx.redirect("/log")),
        ),
        rx.cond(
            AppState.user.role == UserTypes.admin,
            rx.menu.item("Users", on_click=rx.redirect("/users")),
        ),
        rx.cond(
            AppState.user.role == UserTypes.admin,
            rx.menu.item("Feedback", on_click=rx.redirect("/feedback")),
        ),
        rx.cond(
            AppState.user.role == UserTypes.admin,
            rx.menu.item("New Concepts", on_click=rx.redirect("/new_concepts")),
        ),
        rx.cond(
            AppState.user.role == UserTypes.admin,
            rx.menu.item("All Groups", on_click=rx.redirect("/groups")),
        ),
        rx.cond(
            AppState.user.role == UserTypes.admin,
            rx.menu.separator(),
        ),
        rx.menu.item("Log out", on_click=rx.redirect("/logged_out")),
    )


def _logged_out_menu_items() -> rx.Component:
    """Dropdown for an anonymous visitor: just the group onboarding overlay."""
    return rx.menu.item("How this Works", on_click=HowItWorksDialogState.visible)


def user_menu() -> rx.Component:
    """User menu."""
    return rx.menu.root(
        rx.menu.trigger(
            rx.image(src="/menu.svg", width="36px", height="36px", alt="Open menu"),
        ),
        rx.menu.content(
            rx.cond(
                AppState.logged_in,
                _authenticated_menu_items(),
                _logged_out_menu_items(),
            ),
        ),
    )


def app_logo() -> rx.Component:
    """App logo."""
    return rx.flex(
        rx.hstack(
            logo_button(),
            rx.spacer(width="5px"),  # Add spacer after logo
            rx.cond(
                AppState.logged_in,
                rx.hstack(
                    trending_concepts_button(),
                    your_concepts_button(),
                    rx.cond(
                        AppState.logged_in,
                        groups_button(),
                        rx.fragment(),
                    ),
                    legend_button(on_click=LegendDialogState.visible),
                    spacing="5",
                    style={"gap": "24px"},
                    align="center",
                ),
                rx.fragment(),
            ),
            spacing="5",
            style={"gap": "24px"},  # Increased from 18px to 24px
            align="center",
        ),
        rx.spacer(),
        user_menu(),
        align="center",
        width="100%",
        gap="20px",
    )


navbar_styles = dict(
    background="white",
    backdrop_filter="auto",
    backdrop_blur="lg",
    margin="16px 0 8px 0",
    padding="12px 24px",
    border_bottom=f"1px solid {'#fff3'}",
    position="sticky",
    top="0",
    z_index="100",
)


def navbar(*args, **kwargs) -> rx.Component:
    """Navbar component."""
    return rx.box(
        app_logo(),
        feedback_dialog(options=general_feedback_options),
        legend_dialog(),
        how_it_works_dialog(),
        # Hidden trigger the once-per-visit auto-open script clicks for anonymous
        # visitors (kept out of the menu so it's present in the DOM when closed).
        rx.cond(
            AppState.logged_in,
            rx.fragment(),
            rx.button(
                "How this works",
                id="group-howto-open",
                display="none",
                on_click=HowItWorksDialogState.visible,
            ),
        ),
        *args,
        # Poll briefly for the external scrolling.js to define the init fn —
        # without a redirect the navbar can mount before that asset loads.
        on_mount=rx.call_script(
            "(function(){var n=0;(function go(){"
            "if(window.rhizGroupOverlayInit){window.rhizGroupOverlayInit();return;}"
            "if(n++<20)setTimeout(go,100);})();})();"
        ),
        **navbar_styles,
    )
