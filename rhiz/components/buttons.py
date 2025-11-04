import reflex as rx
from rhiz.styles import image_button_style, dialog_button_style

variant = "ghost"

# General button parameters for reuse
button_params = {
    "small": {
        "variant": variant,
        "size": "1",
        "min_width": "28px",
        "min_height": "28px",
        "style": image_button_style,
    },
    "main_menu": {
        "variant": variant,
        "size": "1",
        "style": {
            **image_button_style,
            "padding": "0",
        },
    },
}

_icon_sizes = {
    "small": "24px",
    "main_menu": "24px",
}


def create_button(src, content=None, href=None, button_type="main_menu", **kwargs):
    icon_width = kwargs.pop("icon_width", None)
    icon_height = kwargs.pop("icon_height", None)

    params = button_params[button_type].copy()
    params.update(kwargs)  # Override with any specific kwargs

    default_size = _icon_sizes.get(button_type, "24px")
    icon_width = icon_width or default_size
    icon_height = icon_height or default_size

    button = rx.button(
        rx.image(src=src, width=icon_width, height=icon_height),
        **params,
    )

    if content:  # If there's content, add a tooltip
        button = rx.tooltip(button, content=content)

    if href:  # If there's an href, make it a link
        return rx.link(button, href=href)
    else:
        return button


def logo_button(*args, **kwargs):
    kwargs.setdefault("icon_width", "auto")
    kwargs.setdefault("icon_height", _icon_sizes["main_menu"])
    return create_button("/logo.svg", href="/", button_type="main_menu", **kwargs)


def trending_concepts_button(*args, **kwargs):
    return create_button(
        "/trending_concepts.svg",
        content="Trending Concepts",
        href="/trending_concepts_by_upvotes",
        **kwargs,
    )


def your_concepts_button(*args, **kwargs):
    return create_button(
        "/your_concepts.svg",
        content="Your Concepts",
        href="/your_concepts",
        **kwargs,
    )


def your_drafts_button(*args, **kwargs):
    return create_button(
        "/your_drafts.svg",
        content="Your Drafts",
        button_type="small",
        href="/your_drafts",
        **kwargs,
    )


def legend_button(*args, **kwargs):
    return create_button("/legend.svg", **kwargs)


def submit_button(*args, **kwargs):
    return create_button("/submit.svg", button_type="small", **kwargs)


def close_button(*args, **kwargs):
    return create_button("/close.svg", button_type="small", **kwargs)


def view_parent_button(*args, **kwargs):
    return create_button(
        "/view_parent.svg", content="View Parent", button_type="small", **kwargs
    )


def view_comments_button(*args, **kwargs):
    return create_button(
        "/view_comments.svg", content="View Comments", button_type="small", **kwargs
    )


def disabled_view_comments_button(*args, **kwargs):
    return create_button(
        "/disabled_view_comments.svg",
        content="View Comments",
        button_type="small",
        **kwargs,
    )


def view_concept_button(*args, **kwargs):
    return create_button(
        "/view_concept.svg", content="View Concept", button_type="small", **kwargs
    )


def edit_button(*args, **kwargs):
    return create_button("/edit.svg", content="Edit", button_type="small", **kwargs)


def delete_button(*args, **kwargs):
    return create_button("/delete.svg", content="Delete", button_type="small", **kwargs)


def disabled_edit_button(*args, **kwargs):
    return create_button(
        "/disabled_edit.svg", content="Edit", button_type="small", **kwargs
    )


def disabled_delete_button(*args, **kwargs):
    return create_button(
        "/disabled_delete.svg", content="Delete", button_type="small", **kwargs
    )


def compare_concepts_button(*args, **kwargs):
    return create_button(
        "/compare_concepts.svg", content="Compare", button_type="small", **kwargs
    )


def upvote_concept_button(*args, **kwargs):
    return create_button(
        "/upvote_concept.svg", content="Support", button_type="small", **kwargs
    )


def no_upvote_concept_button(*args, **kwargs):
    return create_button(
        "/no_upvote_concept.svg", content="Support", button_type="small", **kwargs
    )


def downvote_concept_button(*args, **kwargs):
    return create_button(
        "/downvote_concept.svg", content="Detract", button_type="small", **kwargs
    )


def no_downvote_concept_button(*args, **kwargs):
    return create_button(
        "/no_downvote_concept.svg", content="Detract", button_type="small", **kwargs
    )


def support_comment_button(*args, **kwargs):
    return create_button(
        "/support_comment.svg", content="Support", button_type="small", **kwargs
    )


def detract_from_comment_button(*args, **kwargs):
    return create_button(
        "/detract_from_comment.svg", content="Detract", button_type="small", **kwargs
    )


def poo_comment_button(*args, **kwargs):
    return create_button(
        "/poo_comment.svg", content="Point of Order", button_type="small", **kwargs
    )


def feedback_button(*args, **kwargs):
    return create_button(
        "/feedback.svg", content="Feedback", button_type="small", **kwargs
    )


def disabled_feedback_button(*args, **kwargs):
    return create_button(
        "/disabled_feedback.svg", content="Feedback", button_type="small", **kwargs
    )


def more_button(*args, **kwargs):
    return create_button("/more.svg", button_type="small", **kwargs)


def sort_by_upvotes_button(*args, **kwargs):
    return create_button(
        "/sort_by_upvotes.svg",
        content="Sort by Upvotes",
        button_type="small",
        href="/trending_concepts_by_upvotes",
        **kwargs,
    )


def sort_by_support_button(*args, **kwargs):
    return create_button(
        "/sort_by_support.svg",
        content="Sort by Support",
        button_type="small",
        href="/trending_concepts_by_support",
        **kwargs,
    )
