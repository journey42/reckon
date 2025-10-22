"""The home page."""
import reflex as rx
from datetime import datetime, timezone
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.styles import page_params, dialog_button_style
from reckon.components.buttons import submit_button
from reckon.components.container import container
from reckon.components.navbar import navbar
from reckon.components.editor import editor
from reckon.utils.db import insert_text_with_embedding
from reckon.utils.parsing import remove_html_tags

class HomePageState(AppState):
    concept: str = ""

    @rx.event
    def set_concept(self, value: str) -> None:
        self.concept = value or ""

    def post_concept(self, form_data: dict):
        """Post an new reckoning of type concept."""
        if not self.logged_in:
            return rx.window_alert("Please log in to post.")
        content = (form_data.get("concept") or "").strip()
        if content == "":
            return rx.window_alert("A concept cannot be blank.")
        self.concept = content
        with rx.session() as session:
            session.expire_on_commit = False
            #session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;"))
            concept = Reckoning(
                user_id=self.user.id,
                content=self.concept,
                type=ReckoningTypes.draft,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(concept)
            session.commit()
            
        insert_text_with_embedding(remove_html_tags(concept.content), concept.id)
        self._db_updated = True
        return rx.redirect(f"/compare/{concept.id}")

def composer():
    """The composer for new concepts."""
    return rx.form(
        rx.vstack(
            editor(
                name="concept",
                mode="balloon",
                width="100%",
                height="50vh",
                placeholder="What do you Reckon?",
                on_blur=HomePageState.set_concept,
            ),
            submit_button(
                type="submit",
                **dialog_button_style,
            ),
            align="end",
            spacing="4",
            margin="4px",
        ),
        on_submit=HomePageState.post_concept,
        reset_on_submit=True,        
    )


@rx.page(route="/", on_load=HomePageState.check_login(), **page_params)
def home():
    """The home page."""
    return container(
        navbar(),
        composer(),
    )
