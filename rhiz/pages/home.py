"""The home page."""

import reflex as rx
from datetime import datetime, timezone
from rhiz.state.base import AppState, Reckoning, ReckoningTypes
from rhiz.styles import page_params, dialog_button_style
from rhiz.components.container import container
from rhiz.components.navbar import navbar
from rhiz.components.tiptap_editor import TiptapEditor
from rhiz.utils.db import insert_text_with_embedding
from rhiz.utils.parsing import remove_html_tags


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

        content_html = (
            self.concept.replace("&nbsp;", " ").replace("\u00a0", " ").strip()
        )

        plain_text = remove_html_tags(content_html).strip()
        has_media = any(
            tag in content_html.lower()
            for tag in (
                "<img",
                "<video",
                "<iframe",
                "<embed",
                "youtube.com",
                "youtu.be",
            )
        )
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

        yield AppState.set_support_nudge(concept.id, has_matches=False)
        self.concept = ""
        self._db_updated = True
        yield rx.redirect(f"/compare/{concept.id}")


def composer():
    """The composer for new concepts."""
    return rx.vstack(
        rx.box(
            TiptapEditor.create(
                value=HomePageState.concept,
                placeholder="What is your concept?",
                on_change=HomePageState.set_concept,
                height="320px",
                toolbar_enabled=False,
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
