"""Public group page — /group/<slug>.

A group is a standalone founding question with its own concept record and a
dedicated Group row linking it to a slug. The page has three layers:
  1. Group header (name + founding question)
  2. Submission box + related ideas ranked by traction (logged-in only)
  3. Threaded comments section

Anonymous visitors see the header and comments; they cannot submit or see
the similarity-ranked feed until they log in. First-time visitors get a
"how this works" overlay via HowItWorksDialogState.
"""

import reflex as rx
from sqlalchemy.sql import text
from sqlmodel import select
from rhiz.styles import page_params
from rhiz.utils.db import insert_text_with_embedding, find_similar_texts_with_join
from rhiz.utils.groups import get_group_by_slug
from rhiz.pages.reckonings import (
    CommentsPageState,
    page,
    parent_reckoning,
    ReckoningsPageState,
    render_comment,
)
from rhiz.state.base import (
    AppState,
    Reckoning,
    ReckoningTypes,
    UserTypes,
)
from rhiz.components import container, navbar
from rhiz.components.tiptap_editor import TiptapEditor
from rhiz.components.safe_markdown import SafeMarkdown
from rhiz.components.how_it_works_dialog import HowItWorksDialogState
from rhiz.components.concept_dialog import concept_dialog
from rhiz.components.comment_dialog import comment_dialog
from rhiz.components.group_dialog import group_dialog
from rhiz.components.feedback_dialog import feedback_dialog, reckoning_feedback_options
from rhiz.styles import (
    vote_count_and_timestamp_style,
    comment_badge_style,
    read_only_text_style,
)
from rhiz.components.buttons import (
    support_comment_button,
    detract_from_comment_button,
    poo_comment_button,
    upvote_concept_button,
    no_upvote_concept_button,
    downvote_concept_button,
    no_downvote_concept_button,
)


# Traction = up_votes + supports (client confirmation).
TRACTION_COLUMN = "up_votes + supports"


class GroupPageState(CommentsPageState):
    """Group page state: header info, submission, similarity-ranked feed.

    Inherits CommentsPageState for the threaded comments section and the
    shared login/gate logic, but adds group-specific fields and handlers.
    """

    group_name: str = ""
    founding_question: str = ""
    group_not_found: bool = False

    # Submission box state.
    submission_content: str = ""
    submission_type: int = ReckoningTypes.support

    # Related ideas ranked by traction, populated after a submission.
    traction_ideas: list[dict] = []

    @rx.var
    def group_slug(self) -> str:
        return self.get_path_param("slug", "")

    def on_load(self):
        self.page_type = 7
        self.group_not_found = False
        self.parent = None
        self.reckonings = []
        self.concept_id_override = 0
        self.traction_ideas = []

        with rx.session() as session:
            group = get_group_by_slug(session, self.group_slug)
            if group is None:
                self.group_not_found = True
                return
            self.concept_id_override = group.concept_id
            self.group_name = group.name
            self.founding_question = group.founding_question

        self.get_reckonings()
        yield HowItWorksDialogState.set_group_info(
            self.group_name, self.founding_question
        )
        yield self.scroll_to_saved_position()

    @rx.event
    def set_submission_content(self, value: str) -> None:
        self.submission_content = value or ""

    @rx.event
    def set_submission_type(self, t: int) -> None:
        self.submission_type = t

    def _require_login_redirect_for_submission(self):
        """Redirect anonymous users to signup with a group return path."""
        if not self.logged_in:
            target = f"/group/{self.group_slug}"
            from urllib.parse import quote
            return rx.redirect(f"/signup?next={quote(target, safe='/')}")
        if not self.user.enabled:
            return rx.redirect("/login")
        return None

    @rx.event
    def submit_group_answer(self):
        """Submit a support/detract/point-of-order comment under the group's concept.

        After submission:
        1. Create the reckoning (inherited comment flow).
        2. Generate embedding for the content.
        3. Query similar ideas in the same concept.
        4. Rank by traction (up_votes + supports) and set self.traction_ideas.
        """
        result = self._require_login_redirect_for_submission()
        if result:
            return result

        if not self.submission_content.strip():
            return

        with rx.session() as session:
            session.expire_on_commit = False
            # Get the group's concept (parent reckoning).
            concept = session.exec(
                select(Reckoning).where(Reckoning.id == self.concept_id_override)
            ).first()
            if concept is None:
                return

            new_reckoning = Reckoning(
                content=self.submission_content,
                parent_reckoning_id=concept.id,
                type=self.submission_type,
                created_at=concept.created_at,  # Same timestamp as concept
                updated_at=concept.updated_at or concept.created_at,
                user_id=self.user.id,
            )
            session.add(new_reckoning)
            session.commit()

        # Generate embedding for the new submission.
        cleaned_content = self.submission_content.replace("<p>", "").replace(
            "</p>", ""
        ).strip()
        insert_text_with_embedding(cleaned_content, new_reckoning.id)

        # Capture PostHog event for answer submission.
        try:
            from rhiz.rhiz import posthog
            if posthog:
                posthog.capture("group_answer_submitted", distinct_id=f"user-{self.user.id}", properties={
                    "event_type": "answer_submitted",
                    "group_slug": self.group_slug,
                    "content_length": len(self.submission_content),
                    "answer_type": self.submission_type,
                })
        except Exception:
            pass  # PostHog failures should not block submission.

        # Query similar ideas in the same concept, ranked by traction.
        self._load_traction_ideas(concept.id, new_reckoning.id)

        # Clear the submission box and reload comments.
        self.submission_content = ""
        yield self.get_reckonings()
        yield self.scroll_to_saved_position()

    def _load_traction_ideas(self, concept_id: int, my_new_id: int):
        """Load similar ideas in the same concept, ranked by traction."""
        with rx.session() as session:
            # Find similar ideas via embedding similarity.
            keys, results = find_similar_texts_with_join(concept_id, 0.75, 10)

            # Filter to only include ideas under this concept (not the concept itself).
            similar_ids = [pk for pk in keys if pk != concept_id]
            if not similar_ids:
                self.traction_ideas = []
                return

            # Fetch all ideas and compute tallies.
            query = select(Reckoning).where(Reckoning.id.in_(similar_ids))
            rows = session.exec(query).unique().all()
            id_to_reckoning = {r.id: r for r in rows}

            # Compute tallies for each idea.
            for r in rows:
                r.compute_tallies(self.user.id, session=session)

            # Build traction list: (id, reckoning, traction_score).
            traction_list = []
            for rid in similar_ids:
                r = id_to_reckoning.get(rid)
                if r is None:
                    continue
                traction = (r.up_votes or 0) + (r.supports or 0)
                traction_list.append({
                    "id": r.id,
                    "content": r.content,
                    "type": r.type,
                    "up_votes": r.up_votes or 0,
                    "supports": r.supports or 0,
                    "detracts": r.detracts or 0,
                    "points_of_order": r.points_of_order or 0,
                    "elapsed_time": r.elapsed_time or "",
                    "user_vote_history": r.user_vote_history if self.user else ReckoningTypes.no_vote,
                    "traction": traction,
                })

            # Sort by traction desc.
            traction_list.sort(key=lambda x: x["traction"], reverse=True)

            # Insert my new submission at the top (client spec: "starting with your idea at the top").
            self.traction_ideas = [{
                "id": my_new_id,
                "content": self.submission_content,
                "type": self.submission_type,
                "up_votes": 0,
                "supports": 0,
                "detracts": 0,
                "points_of_order": 0,
                "elapsed_time": "",
                "user_vote_history": ReckoningTypes.up_vote if self.submission_type == ReckoningTypes.support else ReckoningTypes.no_vote,
                "traction": 0,
            }] + traction_list


def render_related_idea_card(state: GroupPageState, idea: dict):
    """Render a single related idea card in the traction-ranked feed."""

    # Vote action: upvote the idea (existing behavior — abandons own submission).
    support_action = state.vote_on_concept(idea["id"], ReckoningTypes.up_vote)

    # Button state based on user's vote history.
    should_pulse = (
        state.show_support_nudge
        & (state.support_nudge_concept_id == idea["id"])
        & state.support_button_pulsing
    )
    support_button = no_upvote_concept_button(
        on_click=support_action,
        class_name=rx.cond(should_pulse, "support-pulse", ""),
    )

    # Match icon based on type.
    type_icon = rx.match(
        idea["type"],
        (
            ReckoningTypes.support,
            rx.image(
                src="/support_comment.svg", width="20px", height="20px"
            ),
        ),
        (
            ReckoningTypes.detract,
            rx.image(
                src="/detract_from_comment.svg", width="20px", height="20px"
            ),
        ),
        (
            ReckoningTypes.point_of_order,
            rx.image(
                src="/poo_comment.svg", width="20px", height="20px"
            ),
        ),
    )

    return rx.card(
        rx.flex(
            # Left: idea content.
            rx.vstack(
                rx.grid(
                    type_icon,
                    SafeMarkdown.create(
                        content=idea["content"],
                        class_name="prose",
                        max_width="100%",
                        style={
                            "fontSize": "0.95rem",
                            "color": "#334155",
                        },
                    ),
                    align="start",
                    spacing="2",
                ),
                rx.text(
                    f"↑ {idea['up_votes']}  ↓ {idea['detracts']}  "
                    f"|  Traction: {idea['traction']}",
                    size="1",
                    color="#64748b",
                ),
                align="start",
                spacing="2",
                flex_grow="1",
            ),
            # Right: vote buttons.
            rx.vstack(
                rx.cond(
                    idea["user_vote_history"] == ReckoningTypes.up_vote,
                    upvote_concept_button(on_click=support_action),
                    support_button,
                ),
                rx.text(idea["up_votes"], size="2", font_weight="bold"),
                no_downvote_concept_button(
                    on_click=state.vote_on_concept(
                        idea["id"], ReckoningTypes.down_vote
                    )
                ),
                rx.text(idea["detracts"], size="2", font_weight="bold"),
                spacing="2",
                align="center",
            ),
            direction="row",
            align="center",
            justify="between",
            padding="12px 16px",
        ),
        width="100%",
        margin_bottom="8px",
    )


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
        # Simple page structure - use the existing page() helper from reckonings
        page(GroupPageState, navbar(parent_reckoning(GroupPageState))),
    )




@rx.page(route="/group/[slug]", on_load=GroupPageState.on_load, **page_params)
def group():
    """Public group page (consensus-building layout)."""
    return group_page()
