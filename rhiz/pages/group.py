"""Public group page — /group/<slug>.

A group page functions as a group-specific version of the main site. It
displays:
  1. Group header (name + founding question)
  2. Submission box (answer the framing question as a concept)
  3. Concept feed ordered by traction (up_votes + supports)

Concepts and comments behave exactly as they do on the rest of the site.
Group content is scoped via Reckoning.group_id and is invisible in site-wide
feeds unless the group creator makes it public.
"""

import reflex as rx
from sqlmodel import select, delete
from sqlalchemy import func
from sqlalchemy.orm import noload

from rhiz.styles import page_params, read_only_text_style
from rhiz.utils.db import insert_text_with_embedding
from rhiz.utils.parsing import remove_html_tags
from rhiz.utils.groups import get_group_by_slug
from rhiz.pages.reckonings import (
    ReckoningsPageState,
    page,
)
from rhiz.state.base import Reckoning, ReckoningTypes
from rhiz.components import container, navbar
from rhiz.components.how_it_works_dialog import HowItWorksDialogState
from rhiz.components.tiptap_editor import TiptapEditor
from rhiz.components.buttons import submit_button


class GroupPageState(ReckoningsPageState):
    """Group page state: header info + concept feed.

    Inherits from ReckoningsPageState so vote_on_concept, new_comment,
    compare_concepts, etc. all work identically to the main site.
    """

    group_name: str = ""
    founding_question: str = ""
    group_not_found: bool = False
    group_id_val: int = 0
    founding_concept_id: int = 0
    is_group_public: bool = False

    # Submission box state
    submission_content: str = ""

    @rx.var
    def group_slug(self) -> str:
        return self.get_path_param("slug", "")

    def on_load(self):
        self.page_type = 7
        self.group_not_found = False
        self.reckonings = []
        self.submission_content = ""

        with rx.session() as session:
            group = get_group_by_slug(session, self.group_slug)
            if group is None:
                self.group_not_found = True
                return
            self.group_id_val = group.id
            self.group_name = group.name
            self.founding_question = group.founding_question
            self.founding_concept_id = group.concept_id
            self.is_group_public = group.is_public

        self._load_group_concepts()
        yield HowItWorksDialogState.set_group_info(
            self.group_name, self.founding_question
        )
        yield self.scroll_to_saved_position()

    def _load_group_concepts(self):
        """Load all concepts in this group, ordered by traction desc.

        Excludes the founding question concept (it's already shown as text at
        the top of the page).
        """
        if not self.group_id_val:
            return
        with rx.session() as session:
            query = (
                select(Reckoning)
                .where(
                    Reckoning.group_id == self.group_id_val,
                    Reckoning.type == ReckoningTypes.concept,
                    Reckoning.id != self.founding_concept_id,
                )
                .options(noload(Reckoning.child_reckonings))
            )
            rows = session.exec(query).unique().all()
            Reckoning.assign_tallies_batch(
                rows, self.user.id if self.user else None, session
            )
            # Sort by traction (up_votes + supports) desc, then created_at asc
            rows.sort(
                key=lambda r: (
                    -((r.up_votes or 0) + (r.supports or 0)),
                    r.created_at,
                )
            )
            self.reckonings = rows

    @rx.event
    def set_submission_content(self, value: str) -> None:
        self.submission_content = value or ""

    def close_complete_modal(self):
        yield self._load_group_concepts()

    def delete_reckoning(self, rid):
        """Delete a reckoning. Prevents deletion if it has comments or votes."""
        with rx.session() as session:
            child_count = session.exec(
                select(func.count(Reckoning.id)).where(
                    Reckoning.parent_reckoning_id == rid
                )
            ).first()
            if child_count and child_count > 0:
                return rx.window_alert(
                    "This concept has comments or votes and cannot be deleted. "
                    "Remove all comments and votes first."
                )
            session.exec(delete(Reckoning).where(Reckoning.id == rid))
            session.commit()
        self._load_group_concepts()

    def _require_login_redirect_for_submission(self):
        """Redirect anonymous users to signup with a group return path."""
        if not self.logged_in:
            from urllib.parse import quote

            target = f"/group/{self.group_slug}"
            return rx.redirect(f"/signup?next={quote(target, safe='/')}")
        if not self.user.enabled:
            return rx.redirect("/login")
        return None

    @rx.event
    def submit_group_answer(self):
        """Submit a concept as an answer to the founding question."""
        result = self._require_login_redirect_for_submission()
        if result:
            return result

        if not self.submission_content.strip():
            return

        with rx.session() as session:
            session.expire_on_commit = False
            new_concept = Reckoning(
                content=self.submission_content,
                type=ReckoningTypes.concept,
                group_id=self.group_id_val,
                user_id=self.user.id,
            )
            session.add(new_concept)
            session.commit()

            # Generate embedding for similarity search
            cleaned = remove_html_tags(self.submission_content)
            insert_text_with_embedding(cleaned, new_concept.id)

        # Capture PostHog event
        try:
            from rhiz.rhiz import posthog

            if posthog:
                posthog.capture(
                    "group_answer_submitted",
                    distinct_id=f"user-{self.user.id}",
                    properties={
                        "group_slug": self.group_slug,
                        "content_length": len(self.submission_content),
                    },
                )
        except Exception:
            pass

        # Clear the submission box and reload the concept feed
        self.submission_content = ""
        self._load_group_concepts()
        yield self.scroll_to_saved_position()


def group_page():
    """Render the group page layout."""
    return rx.cond(
        GroupPageState.group_not_found,
        container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Group not found", size="6"),
                    rx.text("This group link is invalid or has been removed."),
                    rx.link("Go to Rhiz", href="/"),
                    spacing="3",
                    align="center",
                ),
                min_height="60vh",
            ),
        ),
        page(
            GroupPageState,
            navbar(),
            # Group header: name + founding question + submission box
            rx.vstack(
                rx.heading(GroupPageState.group_name, size="7"),
                rx.text(
                    "Your group has asked:",
                    size="3",
                    color="#64748b",
                ),
                rx.text(
                    GroupPageState.founding_question,
                    size="5",
                    font_weight="bold",
                    style=read_only_text_style,
                ),
                # Submission box
                rx.box(
                    TiptapEditor.create(
                        value=GroupPageState.submission_content,
                        placeholder="Answer in your own words",
                        height="80px",
                        toolbar_enabled=False,
                        on_change=GroupPageState.set_submission_content,
                    ),
                    width="100%",
                ),
                rx.box(
                    submit_button(
                        on_click=GroupPageState.submit_group_answer,
                    ),
                    width="100%",
                    display="flex",
                    justify_content="flex-end",
                ),
                spacing="3",
                align="stretch",
                width="100%",
                padding="24px",
            ),
        ),
    )


@rx.page(route="/group/[slug]", on_load=GroupPageState.on_load, **page_params)
def group():
    """Public group page (group-specific concept feed)."""
    return group_page()
