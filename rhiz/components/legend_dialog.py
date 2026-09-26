import reflex as rx
from rhiz.state.base import AppState
from rhiz.components.buttons import close_button
from rhiz.styles import dialog_button_style, interior_grid_style

image_params = dict(
    width="28px",
    height="28px",
)


class LegendDialogState(AppState):
    """Legend state."""

    show: bool = False

    def visible(self):
        """Change the visibility of the comment modal."""
        self.show = not (self.show)


def legend_dialog(*args, **kwargs):
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.grid(
                    rx.heading("Legend", size="5"),
                    rx.dialog.close(
                        close_button(
                            **dialog_button_style, on_click=LegendDialogState.visible
                        ),
                        justify_self="end",
                    ),
                    grid_template_columns="1fr auto",
                ),
            ),
            rx.vstack(
                rx.grid(
                    *[rx.hstack(
                        rx.image(src=src, **image_params) if src.endswith(".svg") else rx.icon(name, size=28),
                        rx.text(label),
                        spacing="2",
                        align="center",
                    ) for src, name, label in [
                        ("/menu.svg", "", "Menu"),
                        ("/your_concepts.svg", "", "Your Concepts"),
                        ("/your_drafts.svg", "", "Your Drafts"),
                        ("/trending_concepts.svg", "", "Trending Concepts"),
                        ("", "users", "Your Groups"),
                        ("", "zap", "Live Q&A"),
                        ("/submit.svg", "", "Submit"),
                        ("/compare_concepts.svg", "", "Compare Concepts"),
                        ("/upvote_concept.svg", "", "Upvote Concept"),
                        ("/downvote_concept.svg", "", "Downvote Concept"),
                        ("/view_concept.svg", "", "View Concept"),
                        ("/support_comment.svg", "", "Support Comment"),
                        ("/poo_comment.svg", "", "Point of Order Comment"),
                        ("/detract_from_comment.svg", "", "Detract from Comment"),
                        ("/feedback.svg", "", "Provide Feedback/Report Abuse"),
                        ("/view_parent.svg", "", "View Parent"),
                        ("/view_comments.svg", "", "View Comments"),
                    ]],
                    grid_template_columns="1fr 1fr",
                    **interior_grid_style,
                ),
                display="flex",
                justify_content="center",
                align_items="center",
            ),
        ),
        open=LegendDialogState.show,
        size="4",
        *args,
        **kwargs,
    )
