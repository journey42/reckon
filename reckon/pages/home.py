"""The home page."""
import reflex as rx
from datetime import datetime
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.styles import page_params, input_style
from reckon.components.buttons import submit_button
from ..components import container, navbar
from reckon.utils.db import insert_text_with_embedding

class HomePageState(AppState):
    concept: str

    def post_concept(self):
        """Post an new reckoning of type concept."""
        if not self.logged_in:
            return rx.window_alert("Please log in to post.")
        with rx.session() as session:
            session.expire_on_commit = False
            #session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;"))
            concept = Reckoning(
                user_id=self.user.id,
                content=self.concept,
                type=ReckoningTypes.draft,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(concept)
            session.commit()
            
        insert_text_with_embedding(concept.content, concept.id)
        self._db_updated = True
        return rx.redirect(f"/compare/{concept.id}")

def composer():
    """The composer for new concepts."""
    return rx.grid(
        rx.box(
            rx.text_area(
                w="100%",
                h="50vh",
                placeholder="What do you Reckon?",
                on_blur=HomePageState.set_concept,
                **input_style,
            ),
            rx.hstack(
                submit_button(
                    max_width="48px",
                    max_height="48px",
                    on_click=HomePageState.post_concept
                ),
                justify_content="flex-end",
            ),
        ),
    )


@rx.page(route="/", on_load=HomePageState.check_login(), **page_params)
def home():
    """The home page."""
    return container(
        navbar(),
        rx.grid(
            composer(),
        ),
    )
