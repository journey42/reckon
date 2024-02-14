"""The home page."""
import reflex as rx
from datetime import datetime
from reckon.state.base import AppState, Reckoning, ReckoningTypes
from reckon.styles import button_style, page_params
from ..components import container
from ..components import navbar
from reckon.utils.db import insert_text_with_embedding
#from sqlalchemy import text

class HomePageState(AppState):
    concept: str

    def post_concept(self):
        """Post an new reckoning of type concept."""
        if not self.logged_in:
            return rx.window_alert("Please log in to post.")
        with rx.session() as session:
            session.expire_on_commit = False
            # session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;"))
            concept = Reckoning(
                user_id=self.user.id,
                content=self.concept,
                type=ReckoningTypes.concept,
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
                h="50%",
                background_color="gray.50", border_radius="10px", padding="1em",
                placeholder="What do you Reckon?",
                _focus={"border": 0, "outline": 0, "boxShadow": "none"},
                on_blur=HomePageState.set_concept,
            ),
            rx.hstack(
                rx.button(
                    "Submit",
                    on_click=HomePageState.post_concept,
                    **button_style
                ),
                justify_content="flex-end",
                border_top="1px solid #ededed",
                px=4,
                py=2,
            ),
        ),
        p=4,
        grid_template_columns="1fr",
        border_bottom="1px solid #ededed",
    )


@rx.page(route="/", on_load=HomePageState.check_login(), **page_params)
def home():
    """The home page."""
    return container(
        navbar(),
        rx.grid(
            composer(),
            grid_template_columns="1fr",
            h="100vh",
            gap=4,
        ),
        max_width="1300px",
    )
