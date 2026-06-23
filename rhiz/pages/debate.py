"""Public debate page — the comments view rendered at /debate/<slug>.

A debate is a concept opened for public discussion, so the page IS the normal
comments experience (anonymous read, login-gated write) loaded by the debate's
slug instead of a reckoning id. No redirect: the /debate/<slug> URL renders the
content directly, and first-time visitors are greeted with the debate's title
and intro via the "How this works" overlay.
"""

import reflex as rx

from rhiz.styles import page_params
from rhiz.utils.debates import get_debate_by_slug
from rhiz.pages.reckonings import CommentsPageState, page, parent_reckoning
from rhiz.components import container, navbar
from rhiz.components.how_it_works_dialog import HowItWorksDialogState


class DebatePageState(CommentsPageState):
    """Comments view loaded by debate slug, with a debate-aware greeting."""

    debate_title: str = ""
    debate_intro: str = ""
    debate_not_found: bool = False

    @rx.var
    def debate_slug(self) -> str:
        return self.get_path_param("slug", "")

    def on_load(self):
        self.page_type = 7
        self.debate_not_found = False
        self.parent = None
        self.reckonings = []
        self.concept_id_override = 0
        with rx.session() as session:
            debate = get_debate_by_slug(session, self.debate_slug)
            if debate is None:
                self.debate_not_found = True
                return
            # The inherited comments loader keys off reckoning_id; point it at
            # this debate's concept (instead of the route's slug) before loading.
            self.concept_id_override = debate.concept_id
            self.debate_title = debate.title
            self.debate_intro = debate.intro
        self.get_reckonings()
        yield HowItWorksDialogState.set_debate_info(
            self.debate_title, self.debate_intro
        )
        yield self.scroll_to_saved_position()


def debate_page():
    return rx.cond(
        DebatePageState.debate_not_found,
        container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Debate not found", size="6"),
                    rx.text("This debate link is invalid or has been removed."),
                    rx.link("Go to Rhiz", href="/"),
                    spacing="3",
                    align="center",
                ),
                min_height="60vh",
            ),
        ),
        page(DebatePageState, navbar(parent_reckoning(DebatePageState))),
    )


@rx.page(route="/debate/[slug]", on_load=DebatePageState.on_load, **page_params)
def debate():
    """Public debate page (comments view loaded by slug)."""
    return debate_page()
