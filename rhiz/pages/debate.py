"""Debate share link — redirects /debate/<slug> to the concept's comments page.

A debate is just a concept opened for public discussion; the comments page is
the destination. This route only resolves the slug to its concept and redirects,
so existing share links / QR codes (built as {base}/debate/<slug>) keep working.
"""

import reflex as rx

from rhiz.state.base import AppState
from rhiz.styles import page_params
from rhiz.utils.debates import get_debate_by_slug


class DebatePageState(AppState):
    """Resolves /debate/[slug] and redirects to /comments/<concept_id>."""

    @rx.var
    def debate_slug(self) -> str:
        return self.get_path_param("slug", "")

    def on_load(self):
        with rx.session() as session:
            debate = get_debate_by_slug(session, self.debate_slug)
            if debate is None:
                return rx.redirect("/")
            return rx.redirect(f"/comments/{debate.concept_id}")


@rx.page(route="/debate/[slug]", on_load=DebatePageState.on_load, **page_params)
def debate():
    """Redirects to the concept's comments page (on_load redirects before render)."""
    return rx.center(rx.spinner(), min_height="60vh")
