import reflex as rx
from reckon import styles

variant="unstyled"

small_button_params = dict(
    variant=variant,
    size="xs",
    style=styles.image_button_style,
)

medium_button_params = dict(
    variant=variant,
    size="md",
    style=styles.image_button_style,
)

large_button_params = dict(
    variant=variant,
    size="lg",
    style=styles.image_button_style,
)

logo_button_style = dict(
   # _hover={"bg": reckon_dark_green},
    # display="flex",
    align_items="left",
    justify_content="left",
    width="200px",
    border_radius="50%",
)

xlarge_button_params = dict(
    variant=variant,
    size="lg",
    style=logo_button_style,
)

def logo_button(*args, **kwargs) -> rx.Component:
    return rx.link(
            rx.button(
                rx.image(src="/logo.svg", width="100%", height="100%"),
                **xlarge_button_params,
                **kwargs,
            ),
            href="/",
        )

def new_concepts_button(*args, **kwargs) -> rx.Component:
    return rx.link (
        rx.tooltip(
            rx.button(
                rx.image(src="/new_concepts.svg", width="auto", height="auto"),
                **large_button_params,
                **kwargs,
            ),
            label="New Concepts"
        ),
        href="/new_concepts",
    )

def trending_concepts_button(*args, **kwargs) -> rx.Component:
    return rx.link (
        rx.tooltip(
            rx.button(
                rx.image(src="/trending_concepts.svg", width="auto", height="auto"),
                **large_button_params,
                **kwargs,
            ),
            label="Trending Concepts"
        ),
        href="/trending_concepts",
    )

def your_reckonings_button(*args, **kwargs) -> rx.Component:
    return rx.link (
        rx.tooltip(
            rx.button(
                rx.image(src="/your_reckonings.svg", width="auto", height="auto"),
                **large_button_params,
                **kwargs,
            ),
            label="Your Reckonings"
        ),
        href="/your_reckonings",
    )

def view_parent_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/view_parent.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="View Parent")

def view_children_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/view_children.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="View Children")

def new_comment_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/new_comment.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Edit")

def edit_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/edit.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Edit")

def no_edit_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/no_edit.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Edit")

def delete_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/delete.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Delete")

def no_delete_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/no_delete.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="No Delete")

def compare_concepts_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/compare_concepts.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Compare")

def support_concept_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/support_concept.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Support")

def unsupported_concept_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/unsupported_concept.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Support")

# def view_children_button(*args, **kwargs) -> rx.Component:
#     return rx.tooltip(rx.button(
#         rx.image(src="/comment_on_concept.svg", width="auto", height="auto"),
#         **medium_button_params,
#         **kwargs,
#     ), label="Comment")

def provide_feedback_on_concept_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/feedback.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Feedback")

def detract_from_concept_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/detract_from_concept.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Detract")

def undetracted_concept_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/undetracted_concept.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Detract")

def support_comment_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/support_comment.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Postive")

def detract_from_comment_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/detract_from_comment.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Negative")

def poo_comment_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/poo_comment.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Point of Order")

def feedback_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/feedback.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Feedback")

def no_feedback_button(*args, **kwargs) -> rx.Component:
    return rx.tooltip(rx.button(
        rx.image(src="/no_feedback.svg", width="auto", height="auto"),
        **medium_button_params,
        **kwargs,
    ), label="Feedback")

