"""The home page."""
import reflex as rx
from datetime import datetime, timezone
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.styles import page_params, dialog_button_style
from reckon.components.buttons import submit_button
from reckon.components.container import container
from reckon.components.navbar import navbar
from reflex_suneditor import Editor, EditorOptions, EditorButtonList
from reckon.utils.db import insert_text_with_embedding
from reckon.utils.parsing import remove_html_tags

class HomePageState(AppState):
    concept: str = ""

    @rx.event
    def set_concept(self, value: str) -> None:
        self.concept = value or ""

    @rx.event
    def submit_concept(self):
        """Submit the concept from the editor state."""
        if not self.logged_in:
            return rx.window_alert("Please log in to post.")

        content_html = self.concept.replace("&nbsp;", " ").replace("\u00a0", " ").strip()

        plain_text = remove_html_tags(content_html).strip()
        has_media = any(tag in content_html.lower() for tag in ("<img", "<video", "<iframe", "<embed", "youtube.com", "youtu.be"))
        if not plain_text and not has_media:
            return rx.window_alert("A concept cannot be blank.")

        with rx.session() as session:
            session.expire_on_commit = False
            concept = Reckoning(
                user_id=self.user.id,
                content=content_html,
                type=ReckoningTypes.draft,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(concept)
            session.commit()

        if plain_text:
            insert_text_with_embedding(plain_text, concept.id)
        self.concept = ""
        self._db_updated = True
        return rx.redirect(f"/compare/{concept.id}")

def composer():
    """The composer for new concepts."""
    # Configure the editor options with custom button list to match TipTap
    custom_button_list = [
        ["undo", "redo"],  # Undo/Redo
        ["bold", "italic", "underline", "strike"],  # Text formatting
        ["formatBlock", "fontSize"],  # For headings, paragraph and font size
        ["list", "outdent", "indent"],  # Lists and indentation
        ["blockquote", "horizontalRule"],  # Quotes and dividers
        ["link", "image", "video"],  # Media insertion
        ["removeFormat"],  # Clear formatting
    ]

    editor_options = EditorOptions(
        button_list=custom_button_list,
        default_tag="p",
        mode="classic",
    )

    return rx.vstack(
        rx.box(
            Editor.create(
                set_options=editor_options,
                set_contents=HomePageState.concept,
                placeholder="What do you Reckon?",
                on_change=HomePageState.set_concept,
                height="320px",
                width="100%",
                set_all_plugins=True,
            ),
            class_name="editor-container",
            width="100%",
        ),
        rx.hstack(
            rx.button(
                rx.image(src="/submit.svg", width="24px", height="24px"),
                on_click=HomePageState.submit_concept,
                variant="ghost",
                size="1",
                min_width="28px",
                min_height="28px",
                style=dialog_button_style,
            ),
            justify="end",
            width="100%",
        ),
        align="stretch",
        spacing="6",
        width="100%",
    )


@rx.page(route="/", on_load=HomePageState.check_login(), **page_params)
def home():
    """The home page."""
    return container(
        rx.vstack(
            navbar(),
            rx.box(
                composer(),
                padding_x="24px",
                padding_bottom="32px",
                width="100%",
                background="white",
            ),
            spacing="6",
            align="stretch",
            width="100%",
        ),
    )
# Recompile trigger
