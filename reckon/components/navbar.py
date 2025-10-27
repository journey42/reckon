"""Navbar component for the app."""
import reflex as rx
from reckon.components.buttons import legend_button, trending_concepts_button, your_reckonings_button, logo_button
from reckon.components.feedback_dialog import feedback_dialog, FeedbackDialogState, general_feedback_options
from reckon.components.legend_dialog import legend_dialog, LegendDialogState
from reckon.state.base import AppState, UserTypes

def user_menu() -> rx.Component:
    """User menu."""
    return rx.menu.root(
            rx.menu.trigger(
                rx.avatar(src="/menu.svg", border_color="black.900"),
            ),
            rx.menu.content(
                rx.menu.item(AppState.user.username, disabled=True),
                # rx.menu.item(AppState.user.email, disabled=True),
                rx.menu.separator(),
                # rx.menu.item("Drafts", on_click=rx.redirect("/your_drafts")),
                rx.menu.item("Profile", on_click=rx.redirect("/profile")),
                rx.menu.item("Feedback", on_click=FeedbackDialogState.visible),
                rx.menu.item("About", on_click=rx.redirect("/about")),
                rx.menu.item("How To", on_click=rx.redirect("/how_to")),
                rx.menu.item("Guidelines", on_click=rx.redirect("/guidelines")),
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
                    rx.menu.separator(),
                ),
                rx.menu.item("Log out", on_click=rx.redirect("/logged_out")),
            ),
        )

def app_logo() -> rx.Component:
    """App logo."""
    return rx.flex(
        rx.hstack(
            logo_button(),
            rx.spacer(width="5px"),  # Add spacer after logo
            trending_concepts_button(),
            your_reckonings_button(),
            legend_button(on_click=LegendDialogState.visible),
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
        *args,
        **navbar_styles
    )
