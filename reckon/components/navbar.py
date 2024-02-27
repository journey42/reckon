"""Navbar component for the app."""
import reflex as rx
from .buttons import trending_concepts_button, your_reckonings_button, logo_button
from reckon.components.feedback_dialog import feedback_dialog, FeedbackDialogState, general_feedback_options
from reckon.state.base import AppState, UserTypes
from reckon.styles import interior_grid_style

def user_menu() -> rx.Component:
    """User menu."""
    return rx.menu.root(
            rx.menu.trigger(
                rx.avatar(src="/wind_rose.svg", border_color="black.900"),
            ),
            rx.menu.content(
                rx.menu.item("Drafts", on_click=rx.redirect("/your_drafts")),
                rx.menu.item("Profile", on_click=rx.redirect("/profile")),
                rx.menu.item("Feedback", on_click=FeedbackDialogState.visible),
                rx.menu.item("About", on_click=rx.redirect("/about")),
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
    return rx.grid(
        logo_button(),
        trending_concepts_button(),
        your_reckonings_button(),
        rx.spacer(),
        user_menu(),
        grid_template_columns="1fr 1fr 1fr 20fr 1fr",
        **interior_grid_style
    )

navbar_styles = dict(
    background="white",
    backdrop_filter="auto",
    backdrop_blur="lg",
    margin="16px 0 8px 0",
    padding="4px",
    border_bottom=f"1px solid {'#fff3'}",
    position="sticky",
    top="0",
    z_index="100",
)


def navbar(*args, **kwargs) -> rx.Component:
    """Navbar component."""
    return rx.box(
        rx.grid(
            app_logo(),
            feedback_dialog(options=general_feedback_options),
            *args,
        ),
        **navbar_styles
    )