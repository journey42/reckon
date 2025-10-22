import reflex as rx
from reckon.state.base import AppState
from reckon.components.buttons import close_button
from reckon.styles import dialog_button_style, interior_grid_style

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
                    rx.spacer(),
                    rx.dialog.close(
                        close_button(
                            **dialog_button_style,
                            on_click=LegendDialogState.visible
                        ),
                    ),
                    grid_template_columns="3fr 5fr 1fr",
                ),
            ),
            rx.vstack(
                rx.grid(
                    rx.image(src="/menu.svg", **image_params), rx.text("Menu"),
                    rx.image(src="/your_reckonings.svg", **image_params), rx.text("Your Reckonings"),
                    rx.image(src="/your_drafts.svg", **image_params), rx.text("Your Drafts"),
                    rx.image(src="/trending_concepts.svg", **image_params), rx.text("Trending Concepts"),
                    rx.image(src="/submit.svg", **image_params), rx.text("Submit"),
                    rx.image(src="/compare_concepts.svg", **image_params), rx.text("Compare Concepts"),
                    rx.image(src="/upvote_concept.svg", **image_params), rx.text("Upvote Concept"),
                    rx.image(src="/downvote_concept.svg", **image_params), rx.text("Downvote Concept"),
                    rx.image(src="/view_concept.svg", **image_params), rx.text("View Concept"),
                    rx.image(src="/support_comment.svg", **image_params), rx.text("Support Comment"),
                    rx.image(src="/poo_comment.svg", **image_params), rx.text("Point of Order Comment"),
                    rx.image(src="/detract_from_comment.svg", **image_params), rx.text("Detract from Comment"),
                    rx.image(src="/feedback.svg", **image_params), rx.text("Provide Feedback/Report Abuse"),
                    rx.image(src="/view_parent.svg", **image_params), rx.text("View Parent"),
                    rx.image(src="/view_comments.svg", **image_params), rx.text("View Comments"),
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
        **kwargs
    )
