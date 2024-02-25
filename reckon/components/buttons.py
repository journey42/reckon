import reflex as rx
from reckon import styles

variant = "unstyled"

# General button parameters for reuse
button_params = {
    "small": {
        "variant": variant,
        "size": "xs",
        "width": "15%",
        "height": "15%",
        "style": styles.image_button_style,
    },
    "main_menu": {
        "variant": variant,
        "size": "xs",
        "style": styles.image_button_style,
    },
}

def create_button(src, label=None, href=None, button_type="main_menu", **kwargs):
    # Choose button parameters based on type
    params = button_params[button_type].copy()
    params.update(kwargs)  # Override with any specific kwargs

    button = rx.button(rx.image(src=src, width="auto", height="auto"), **params)

    if label:  # If there's a label, add a tooltip
        button = rx.tooltip(button, label=label)

    if href:  # If there's an href, make it a link
        return rx.link(button, href=href)
    else:
        return button

def logo_button(*args, **kwargs):
    return create_button("/logo.webp", href="/", button_type="main_menu", width="150px", **kwargs)

def trending_concepts_button(*args, **kwargs):
    return create_button("/trending_concepts.webp", label="Trending Concepts", href="/trending_concepts", **kwargs)

def your_reckonings_button(*args, **kwargs):
    return create_button("/your_reckonings.svg", label="Your Reckonings", href="/your_reckonings", **kwargs)

def your_drafts_button(*args, **kwargs):
    return create_button("/your_drafts.svg", label="Your Drafts", href="/your_drafts", **kwargs)

def submit_button(*args, **kwargs):
    return create_button("/submit.svg", button_type="small", **kwargs)

def close_button(*args, **kwargs):
    return create_button("/close.svg", button_type="small", **kwargs)

def view_parent_comment_button(*args, **kwargs):
    return create_button("/view_parent_comment.webp", label="View Parent", button_type="small", **kwargs)

def view_comments_button(*args, **kwargs):
    return create_button("/view_comments.webp", label="View Comments", button_type="small", **kwargs)

def view_concept_button(*args, **kwargs):
    return create_button("/view_concept.svg", label="View Concept", button_type="small", **kwargs)

def edit_button(*args, **kwargs):
    return create_button("/edit.svg", label="Edit", button_type="small", **kwargs)

def delete_button(*args, **kwargs):
    return create_button("/delete.svg", label="Delete", button_type="small", **kwargs)

def compare_concepts_button(*args, **kwargs):
    return create_button("/compare_concepts.svg", label="Compare", button_type="small", **kwargs)

def up_vote_concept_button(*args, **kwargs):
    return create_button("/up_vote_concept.webp", label="Support", button_type="small", **kwargs)

def no_up_vote_concept_button(*args, **kwargs):
    return create_button("/no_up_vote_concept.webp", label="Support", button_type="small", **kwargs)

def down_vote_concept_button(*args, **kwargs):
    return create_button("/down_vote_concept.webp", label="Detract", button_type="small", **kwargs)

def no_down_vote_concept_button(*args, **kwargs):
    return create_button("/no_down_vote_concept.webp", label="Detract", button_type="small", **kwargs)

def support_comment_button(*args, **kwargs):
    return create_button("/support_comment.webp", label="Positive", button_type="small", **kwargs)

def detract_from_comment_button(*args, **kwargs):
    return create_button("/detract_from_comment.webp", label="Negative", button_type="small", **kwargs)

def poo_comment_button(*args, **kwargs):
    return create_button("/poo_comment.webp", label="Point of Order", button_type="small", **kwargs)

def feedback_button(*args, **kwargs):
    return create_button("/feedback.svg", label="Feedback", button_type="small", **kwargs)
