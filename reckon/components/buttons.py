import reflex as rx
from reckon.styles import image_button_style, dialog_button_style

variant = "ghost"

# General button parameters for reuse
button_params = {
    "small": {
        "variant": variant,
        "size":"1",
        "min_width": "28px",
        "min_height": "28px",
        "style": image_button_style,
    },
    "main_menu": {
        "variant": variant,
        "size":"1",
        "min_width": "36px",
        "min_height": "36px",
        "style": image_button_style,
    },
}

def create_button(src, content=None, href=None, button_type="main_menu", **kwargs):
    # Choose button parameters based on type
    params = button_params[button_type].copy()
    params.update(kwargs)  # Override with any specific kwargs

    button = rx.button(rx.image(src=src, width="auto", height="auto"), **params)

    if content:  # If there's content, add a tooltip
        button = rx.tooltip(button, content=content)

    if href:  # If there's an href, make it a link
        return rx.link(button, href=href)
    else:
        return button

def logo_button(*args, **kwargs):
    return create_button("/logo.webp", href="/", button_type="main_menu", width="168px", height="36px", **kwargs)

def trending_concepts_button(*args, **kwargs):
    return create_button("/trending_concepts.webp", content="Trending Concepts", href="/trending_concepts_by_upvotes", **kwargs)

def your_reckonings_button(*args, **kwargs):
    return create_button("/your_reckonings.svg", content="Your Reckonings", href="/your_reckonings", **kwargs)

def your_drafts_button(*args, **kwargs):
    return create_button("/your_drafts.svg", content="Your Drafts", button_type="small", href="/your_drafts", **kwargs)

def legend_button(*args, **kwargs):
    return create_button("/legend.svg", **kwargs)

def submit_button(*args, **kwargs):
    return create_button("/submit.webp", button_type="small", **kwargs)

def close_button(*args, **kwargs):
    return create_button("/close.webp", button_type="small", **kwargs)

def view_parent_button(*args, **kwargs):
    return create_button("/view_parent.webp", content="View Parent", button_type="small", **kwargs)

def view_comments_button(*args, **kwargs):
    return create_button("/view_comments.webp", content="View Comments", button_type="small", **kwargs)

def disabled_view_comments_button(*args, **kwargs):
    return create_button("/disabled_view_comments.webp", content="View Comments", button_type="small", **kwargs)

def view_concept_button(*args, **kwargs):
    return create_button("/view_concept.webp", content="View Concept", button_type="small", **kwargs)

def edit_button(*args, **kwargs):
    return create_button("/edit.webp", content="Edit", button_type="small", **kwargs)

def delete_button(*args, **kwargs):
    return create_button("/delete.webp", content="Delete", button_type="small", **kwargs)

def disabled_edit_button(*args, **kwargs):
    return create_button("/disabled_edit.webp", content="Edit", button_type="small", **kwargs)

def disabled_delete_button(*args, **kwargs):
    return create_button("/disabled_delete.webp", content="Delete", button_type="small", **kwargs)

def compare_concepts_button(*args, **kwargs):
    return create_button("/compare_concepts.webp", content="Compare", button_type="small", **kwargs)

def upvote_concept_button(*args, **kwargs):
    return create_button("/upvote_concept.webp", content="Support", button_type="small", **kwargs)

def no_upvote_concept_button(*args, **kwargs):
    return create_button("/no_upvote_concept.webp", content="Support", button_type="small", **kwargs)

def downvote_concept_button(*args, **kwargs):
    return create_button("/downvote_concept.webp", content="Detract", button_type="small", **kwargs)

def no_downvote_concept_button(*args, **kwargs):
    return create_button("/no_downvote_concept.webp", content="Detract", button_type="small", **kwargs)

def support_comment_button(*args, **kwargs):
    return create_button("/support_comment.webp", content="Support", button_type="small", **kwargs)

def detract_from_comment_button(*args, **kwargs):
    return create_button("/detract_from_comment.webp", content="Detract", button_type="small", **kwargs)

def poo_comment_button(*args, **kwargs):
    return create_button("/poo_comment.webp", content="Point of Order", button_type="small", **kwargs)

def feedback_button(*args, **kwargs):
    return create_button("/feedback.webp", content="Feedback", button_type="small", **kwargs)

def disabled_feedback_button(*args, **kwargs):
    return create_button("/disabled_feedback.webp", content="Feedback", button_type="small", **kwargs)

def more_button(*args, **kwargs):
    return create_button("/more.webp", button_type="small", **kwargs)

def sort_by_upvotes_button(*args, **kwargs):
    return create_button("/sort_by_upvotes.webp", content="Sort by Upvotes", button_type="small", href="/trending_concepts_by_upvotes", **kwargs)

def sort_by_support_button(*args, **kwargs):
    return create_button("/sort_by_support.webp", content="Sort by Support", button_type="small", href="/trending_concepts_by_support", **kwargs)


