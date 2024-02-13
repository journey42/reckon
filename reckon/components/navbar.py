"""Navbar component for the app."""
import reflex as rx
from reckon.styles import control_panel_text_style
from .buttons import new_concepts_button, trending_concepts_button, your_reckonings_button, logo_button
from .general_feedback_modal import general_feedback_modal, GeneralFeedbackModalState
from reckon.state.base import AppState, UserTypes

def user_menu() -> rx.Component:
    """User menu."""
    return rx.menu(
            rx.menu_button(
                rx.avatar(src="/wind_rose.svg", border_color="black.900"),
            ),
            rx.menu_list(
                rx.link(
                    rx.menu_item("Help"),
                    href="/help"
                ),
                rx.link(
                    rx.menu_item("Profile"),
                    href="/profile"
                ),
                rx.menu_item("Feedback", on_click=GeneralFeedbackModalState.visible),
                rx.link(
                    rx.menu_item("About"),
                    href="/about"
                ),
                rx.link(
                    rx.menu_item("Guidelines"),
                    href="/guidelines"
                ),
                rx.link(
                    rx.menu_item("Terms"),
                    href="/terms"
                ),
                rx.link(
                    rx.menu_item("Privacy"),
                    href="/privacy"
                ),
                rx.cond(
                    AppState.user.role == UserTypes.admin,
                    rx.menu_divider(),
                ),
                rx.cond(
                    AppState.user.role == UserTypes.admin,
                    rx.link(
                        rx.menu_item("Logs"),
                        href="/logs"
                    )
                ),
                rx.cond(
                    AppState.user.role == UserTypes.admin,
                    rx.link(
                        rx.menu_item("Users"),
                        href="/users"
                    )
                ),
                rx.cond(
                    AppState.user.role == UserTypes.admin,
                    rx.link(
                        rx.menu_item("Feedback"),
                        href="/feedback"
                    )
                ),
                rx.cond(
                    AppState.user.role == UserTypes.admin,
                    rx.menu_divider(),
                ),
                rx.link(
                    rx.menu_item("Log out"),
                    href="/logged_out"
                )
            ),
        )


def app_logo() -> rx.Component:
    """App logo."""
    return rx.grid(
        logo_button(),
        new_concepts_button(),
        trending_concepts_button(),
        your_reckonings_button(),
        rx.spacer(),
        grid_template_columns="0.25fr 1fr 1fr 1fr 8fr",
        py=2,
        px=2,
        gap=2,
        # **control_panel_text_style,
    )

navbar_styles = dict(
    bg="white",
    backdrop_filter="auto",
    backdrop_blur="lg",
    p="4",
    border_bottom=f"1px solid {'#fff3'}",
    position="sticky",
    top="0",
    z_index="100",
)


def navbar(*args, **kwargs) -> rx.Component:
    """Navbar component."""
    return rx.box(
        rx.grid(
            rx.grid(
                app_logo(),
                rx.spacer(),
                user_menu(),
                general_feedback_modal(),
                grid_template_columns="10fr 3fr 1fr",
                py=2,
                px=2,
                gap=2,
                **control_panel_text_style,
            ),
            *args,
        ),
        **navbar_styles
    )