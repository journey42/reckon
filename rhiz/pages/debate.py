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

    def _signup_redirect(self):
        """Redirect anonymous users to signup with a return to this debate."""
        return rx.redirect(f"/signup?next=/debate/{self.debate_slug}")

    def go_comment(self):
        if not self.logged_in:
            return self._signup_redirect()
        return rx.redirect(f"/comments/{self.concept.id}")

    def go_compare(self):
        if not self.logged_in:
            return self._signup_redirect()
        return rx.redirect(f"/compare/{self.concept.id}")

    def go_propose(self):
        if not self.logged_in:
            return self._signup_redirect()
        return rx.redirect("/")


from rhiz.components.safe_markdown import SafeMarkdown
from rhiz.components import container
from rhiz.styles import read_only_text_style, page_params


def _howto_overlay():
    """How-this-works modal: hidden trigger (#debate-howto-open) auto-clicked
    once per slug by assets/scrolling.js; visible CTA reopens it."""
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                "How this works",
                id="debate-howto-open",
                size="2",
                variant="soft",
            ),
        ),
        rx.dialog.content(
            rx.dialog.title("How this works"),
            rx.dialog.description(
                "This page shows a concept open for debate. Anyone can read it "
                "and the responses below. To add a comment, compare it with "
                "similar ideas, or propose your own alternative, create a free "
                "account — your contribution then joins the wider debate on the "
                "site.",
                size="2",
            ),
            rx.dialog.close(
                rx.button("Got it", margin_top="12px"),
            ),
            max_width="480px",
        ),
    )


def _comment(c: Reckoning):
    return rx.box(
        SafeMarkdown.create(
            content=c.content,
            class_name="prose",
            max_width="100%",
            **read_only_text_style,
        ),
        margin_left=c.depth,
        padding_y="6px",
        border_left="2px solid #eaecf0",
        padding_left="10px",
    )


def _gated_cta(state):
    """Login-gated action buttons (anonymous -> signup with return)."""
    return rx.hstack(
        rx.button(
            "Comment",
            on_click=state.go_comment,
        ),
        rx.button(
            "Compare concepts",
            on_click=state.go_compare,
            variant="soft",
        ),
        rx.button(
            "Propose an alternative",
            on_click=state.go_propose,
            variant="soft",
        ),
        spacing="3",
        wrap="wrap",
    )


def debate_page():
    return container(
        rx.cond(
            DebatePageState.not_found,
            rx.center(
                rx.vstack(
                    rx.heading("Debate not found", size="6"),
                    rx.text("This debate link is invalid or has been removed."),
                    rx.link("Go to Rhiz", href="/"),
                    spacing="3",
                ),
                min_height="60vh",
            ),
            rx.vstack(
                rx.hstack(
                    rx.heading(DebatePageState.debate_title, size="7"),
                    rx.spacer(),
                    _howto_overlay(),
                    width="100%",
                    align="center",
                ),
                rx.text(
                    DebatePageState.debate_intro,
                    size="3",
                    style={"whiteSpace": "pre-line", "color": "#475569"},
                ),
                rx.divider(),
                rx.box(
                    SafeMarkdown.create(
                        content=DebatePageState.concept.content,
                        class_name="prose",
                        max_width="100%",
                        **read_only_text_style,
                    ),
                    width="100%",
                ),
                rx.cond(
                    DebatePageState.is_open,
                    _gated_cta(DebatePageState),
                    rx.callout(
                        "This debate is closed to new contributions.",
                        size="1",
                    ),
                ),
                rx.divider(),
                rx.heading("Responses", size="4"),
                rx.foreach(DebatePageState.comments, _comment),
                spacing="4",
                align="stretch",
                width="100%",
                padding="24px",
                on_mount=rx.call_script(
                    "window.rhizDebateOverlayInit && window.rhizDebateOverlayInit();"
                ),
            ),
        ),
    )


@rx.page(route="/debate/[slug]", on_load=DebatePageState.on_load, **page_params)
def debate():
    """Public debate page."""
    return debate_page()
