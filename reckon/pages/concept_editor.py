"""comment editor modal component."""
import reflex as rx
from datetime import datetime
from sqlmodel import select
from reckon.styles import button_style, page_params, control_panel_text_style
from reckon.state.base import AppState, Reckoning
from reckon.components.navbar import navbar

class ConceptEditorPageState(AppState):
    """Concept editor state."""
    concept: Reckoning = None
    content: str = ""

    def get_concept(self, cid):
        """Get reckoning with id of cid from the database."""
        with rx.session() as session:
                self.concept = session.exec(select(Reckoning).where(Reckoning.id == cid)).first()

    def on_load(self):
        self.check_login()
        self.get_concept(self.concept_id)
        self.content = self.concept.content

    @rx.var
    def concept_id(self):
        return self.router.page.params.get('cid', None)

    def submit(self):
        """Submit concept."""
        with rx.session() as session:
            session.expire_on_commit = False
            self.concept = session.merge(self.concept)
            self.concept.content = self.content
            self.concept.updated_at = datetime.utcnow()
            session.commit()

        self.content = ""
        yield rx.redirect(f'/concept/{self.concept_id}')

def edit_control():
    return rx.box(
            rx.grid(
                rx.grid(
                    rx.heading("Concept", size="sm"),
                    rx.spacer(),
                    rx.text("x", on_click=rx.redirect(f'/concept/{ConceptEditorPageState.concept_id}'), style={"cursor": "pointer"}),
                    grid_template_columns="3fr 5fr 0.25fr",
                ),
                rx.grid(
                    rx.text_area(
                        default_value=ConceptEditorPageState.content,
                        placeholder="Concept",
                        width="98%", height="98%", overflow="hidden", background_color="gray.50", border_radius="10px", padding="1em",
                        on_blur=ConceptEditorPageState.set_content,
                    ),
                    gap="2",
                ),
                rx.grid(
                    rx.spacer(),
                    rx.spacer(),
                    rx.button(
                        "Submit",
                        on_click=ConceptEditorPageState.submit,
                        **button_style
                    ),
                    grid_template_columns="3fr 6fr 1fr",
                    **control_panel_text_style,
                ),
                gap=4,
                padding=2,
            ),
            width="100%",
            border="1px solid #ededed",
    )

@rx.page(route="/concept_editor/[cid]", on_load=ConceptEditorPageState.on_load, **page_params)
def concept_editor():
    """Concept Editor."""
    return rx.container(
        navbar(),
        edit_control(),
        max_width="1300px",
    )
