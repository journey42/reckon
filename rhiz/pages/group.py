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
from rhiz.utils.db import insert_text_with_embedding, find_similar_texts_with_join
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
from rhiz.components.safe_markdown import SafeMarkdown


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
    is_group_owner: bool = False

    # Submission box state
    submission_content: str = ""

    # Decision fork: similar concepts shown alongside the user's new submission
    nudge_similar: list[dict] = []
    nudge_new_concept_id: int = 0

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
            self.is_group_owner = group.created_by == self.user.id if self.user else False

        self._load_group_concepts()
        yield HowItWorksDialogState.set_group_info(
            self.group_name, self.founding_question
        )
        return rx.call_script("scrollToSavedPosition();")

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

            # Compute traction for each concept
            for r in rows:
                r.similarity = float((r.up_votes or 0) + (r.supports or 0))

            # Group concepts by semantic similarity clusters.
            # Each concept is compared against cluster representatives; if
            # similar (distance < 0.5), it joins that cluster. Otherwise it
            # starts a new cluster. Clusters are ordered by the traction of
            # their top concept; within a cluster, by traction desc.
            if len(rows) > 1:
                from rhiz.utils.db import find_similar_texts_with_join

                cluster_reps = []  # list of (rep_concept, [cluster_members])
                for r in rows:
                    placed = False
                    if cluster_reps:
                        keys, _ = find_similar_texts_with_join(
                            r.id, 0.6, len(cluster_reps) + 1,
                            group_id=self.group_id_val,
                        )
                        similar_ids = set(keys) - {r.id}
                        for i, (rep, members) in enumerate(cluster_reps):
                            if rep.id in similar_ids:
                                members.append(r)
                                placed = True
                                break
                    if not placed:
                        cluster_reps.append((r, [r]))

                # Sort clusters by traction of their representative (highest first)
                cluster_reps.sort(
                    key=lambda c: -float(
                        (c[0].up_votes or 0) + (c[0].supports or 0)
                    )
                )

                # Flatten: within each cluster, sort by traction desc
                ordered = []
                for rep, members in cluster_reps:
                    members.sort(
                        key=lambda r: (
                            -((r.up_votes or 0) + (r.supports or 0)),
                            r.created_at,
                        )
                    )
                    ordered.extend(members)
                rows = ordered
            else:
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

    @rx.event
    def nudge_support_concept(self, concept_id: int):
        """Upvote a specific concept from the decision fork."""
        self.dismiss_support_nudge()
        with rx.session() as session:
            session.expire_on_commit = False
            existing_vote = session.exec(
                select(Reckoning).where(
                    Reckoning.parent_reckoning_id == concept_id,
                    Reckoning.user_id == self.user.id,
                    Reckoning.type.in_([ReckoningTypes.up_vote, ReckoningTypes.down_vote]),
                )
            ).first()
            if existing_vote:
                if existing_vote.type != ReckoningTypes.up_vote:
                    existing_vote.type = ReckoningTypes.up_vote
                    session.add(existing_vote)
                    session.commit()
            else:
                vote = Reckoning(
                    content="n/a",
                    parent_reckoning_id=concept_id,
                    type=ReckoningTypes.up_vote,
                    user_id=self.user.id,
                )
                session.add(vote)
                session.commit()
        self._load_group_concepts()

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

    def graduate_concept(self, rid: int):
        """Graduate a group concept to the main site by clearing its group_id.
        Only the group creator can graduate concepts.
        """
        if not self.is_group_owner:
            return
        with rx.session() as session:
            session.expire_on_commit = False
            concept = session.exec(
                select(Reckoning).where(Reckoning.id == rid)
            ).first()
            if concept is not None and concept.group_id == self.group_id_val:
                concept.group_id = None
                session.add(concept)
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
        """Submit a concept as an answer to the founding question.

        After creating the concept:
        - If similar concepts exist in the group, show a decision fork
          (upvote your own or switch support to an existing one).
        - If no similar concepts, auto-upvote the user's own concept so it
          doesn't appear with zero support.
        """
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

        # Check for similar concepts within this group (lower threshold for grouping)
        similar_keys, _ = find_similar_texts_with_join(
            new_concept.id, 0.6, 10, group_id=self.group_id_val
        )
        similar_ids = [k for k in similar_keys if k != new_concept.id]
        has_matches = bool(similar_ids)

        if has_matches:
            # Show the decision fork: load similar concepts for display
            self.nudge_new_concept_id = new_concept.id
            self.nudge_similar = []
            with rx.session() as session:
                similar_rows = session.exec(
                    select(Reckoning).where(Reckoning.id.in_(similar_ids))
                ).all()
                Reckoning.assign_tallies_batch(
                    similar_rows, self.user.id, session
                )
                for r in similar_rows:
                    self.nudge_similar.append({
                        "id": r.id,
                        "content": r.content,
                        "up_votes": r.up_votes or 0,
                        "supports": r.supports or 0,
                    })
            self.show_support_nudge = True
            self.support_nudge_concept_id = new_concept.id
            self.nudge_has_matches = True
            self.support_nudge_collapsed = False
            self.support_button_pulsing = True
        else:
            # No similar concepts — auto-upvote the user's own concept
            with rx.session() as session:
                session.expire_on_commit = False
                auto_vote = Reckoning(
                    content="n/a",
                    parent_reckoning_id=new_concept.id,
                    type=ReckoningTypes.up_vote,
                    user_id=self.user.id,
                )
                session.add(auto_vote)
                session.commit()

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
                        "has_matches": has_matches,
                    },
                )
        except Exception:
            pass

        # Clear the submission box and reload the concept feed
        self.submission_content = ""
        self._load_group_concepts()


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
                # Decision fork: shows when a submitted concept has similar matches
                rx.cond(
                    GroupPageState.show_support_nudge
                    & GroupPageState.nudge_has_matches,
                    rx.vstack(
                        rx.text(
                            "Your idea is related to existing concepts. "
                            "Choose which to support:",
                            size="3",
                            weight="medium",
                            color="#475569",
                        ),
                        # The user's new concept
                        rx.card(
                            rx.flex(
                                rx.text(
                                    "Your submission",
                                    size="1",
                                    color="#64748b",
                                ),
                                rx.button(
                                    "Support mine",
                                    size="1",
                                    variant="solid",
                                    on_click=GroupPageState.nudge_support_concept(
                                        GroupPageState.nudge_new_concept_id
                                    ),
                                ),
                                direction="row",
                                justify="between",
                                align="center",
                                width="100%",
                            ),
                            width="100%",
                        ),
                        # Similar concepts
                        rx.foreach(
                            GroupPageState.nudge_similar,
                            lambda s: rx.card(
                                rx.flex(
                                    rx.vstack(
                                        SafeMarkdown.create(
                                            content=s["content"],
                                            class_name="prose",
                                            max_width="100%",
                                            style={
                                                "fontSize": "0.9rem",
                                                "color": "#334155",
                                            },
                                        ),
                                        rx.hstack(
                                            rx.text("↑ ", size="1", color="#64748b"),
                                            rx.text(s["up_votes"], size="1", color="#64748b"),
                                            rx.text("  ♥ ", size="1", color="#64748b"),
                                            rx.text(s["supports"], size="1", color="#64748b"),
                                            spacing="0",
                                        ),
                                        spacing="1",
                                        flex_grow="1",
                                    ),
                                    rx.button(
                                        "Support this",
                                        size="1",
                                        variant="soft",
                                        color_scheme="green",
                                        on_click=GroupPageState.nudge_support_concept(
                                            s["id"]
                                        ),
                                    ),
                                    direction="row",
                                    justify="between",
                                    align="center",
                                    width="100%",
                                    gap="12px",
                                ),
                                width="100%",
                            ),
                        ),
                        rx.button(
                            "Decide later",
                            size="1",
                            variant="soft",
                            color_scheme="gray",
                            on_click=GroupPageState.dismiss_support_nudge,
                        ),
                        spacing="2",
                        align="stretch",
                        width="100%",
                        padding="12px",
                        border="1px solid #e2e8f0",
                        border_radius="12px",
                        background="#f8fafc",
                    ),
                    rx.fragment(),
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
