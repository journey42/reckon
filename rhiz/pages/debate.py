"""Public debate page — anonymous read, login-gated write."""

import reflex as rx
from typing import Optional
from sqlmodel import select

from rhiz.state.base import AppState, Reckoning, ReckoningTypes, Debate, DebateStatus
from rhiz.utils.debates import get_debate_by_slug


class DebatePageState(AppState):
    """State for the public /debate/[slug] page. on_load does NOT require login."""

    not_found: bool = False
    debate_title: str = ""
    debate_intro: str = ""
    debate_status: str = DebateStatus.open
    concept: Optional[Reckoning] = None
    comments: list[Reckoning] = []

    @rx.var
    def debate_slug(self) -> str:
        return self.get_path_param("slug", "")

    @rx.var
    def is_open(self) -> bool:
        return self.debate_status == DebateStatus.open

    def on_load(self):
        """Public load: resolve the debate by slug; no auth required."""
        self.not_found = False
        self.concept = None
        self.comments = []
        with rx.session() as session:
            debate = get_debate_by_slug(session, self.debate_slug)
            if debate is None:
                self.not_found = True
                return
            self.debate_title = debate.title
            self.debate_intro = debate.intro
            self.debate_status = debate.status
            concept = session.exec(
                select(Reckoning).where(Reckoning.id == debate.concept_id)
            ).first()
            if concept is None:
                self.not_found = True
                return
            Reckoning.assign_tallies_batch(
                [concept], self.user.id if self.user else None, session
            )
            self.concept = concept
            self.comments = self._load_comment_tree(session, debate.concept_id)

    def _load_comment_tree(self, session, root_id, depth=0, max_depth=3):
        """Flat, depth-tagged list of non-vote descendants (read-only display)."""
        out: list[Reckoning] = []
        children = session.exec(
            select(Reckoning)
            .where(Reckoning.parent_reckoning_id == root_id)
            .where(
                Reckoning.type.notin_(
                    [ReckoningTypes.up_vote, ReckoningTypes.down_vote]
                )
            )
            .order_by(Reckoning.created_at)
        ).all()
        for child in children:
            child.depth = "4px" if depth == 0 else f"{depth * 20}px"
            out.append(child)
            if depth < max_depth - 1:
                out.extend(
                    self._load_comment_tree(session, child.id, depth + 1, max_depth)
                )
        return out

    def require_login_then(self, path: str):
        """If logged in, go to `path`; otherwise to signup with a return URL."""
        if self.logged_in:
            return rx.redirect(path)
        return rx.redirect(f"/signup?next=/debate/{self.debate_slug}")
