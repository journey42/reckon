"""Feed row actions must stay reachable.

Comment entry points silently disappeared from feed concept rows during the
July group-feed rework: the buttons existed only on the /comments/<id> detail
page, so users in a group could vote on a concept but had no way to comment on
it, and the site recorded zero comments for two months without any error
anywhere. These tests pin the invariants that would have caught it.
"""

import inspect

from rhiz.pages.group import GroupPageState
import rhiz.state.auth as auth_state
from rhiz.pages import reckonings


def test_feed_concept_rows_offer_comment_buttons():
    """The concept itself is the comment button (client request); points of
    order and detracts keep their own buttons in feed rows."""
    src = inspect.getsource(reckonings.render_concept_template)
    assert (
        "state.new_comment(content, ReckoningTypes.support, item_id)" in src
    ), "the concept content is no longer wired to the comment dialog"
    assert "cursor=\"pointer\"" in src, "concept content is not visibly clickable"
    for button in ("poo_comment_button", "detract_from_comment_button"):
        assert button in src, f"{button} missing from feed rows"
    # The old separate support-comment CTA must be gone from the row.
    assert "support_comment_button" not in src, (
        "the concept is the comment button now — remove the separate CTA"
    )


def test_render_concept_enables_comments():
    src = inspect.getsource(reckonings.render_concept)
    assert "allow_comments=True" in src


def test_vote_rows_do_not_enable_comments():
    # render_vote must keep the default (False): a vote row is about its
    # parent, and commenting there would attach to the wrong object.
    src = inspect.getsource(reckonings.render_vote)
    assert "allow_comments" not in src


def test_feed_action_rows_wrap_instead_of_using_fixed_grids():
    """Fixed-track grids cannot shrink below the button icons' widths, so on
    320-390px phones the rightmost actions (detract, feedback) landed past the
    viewport edge. The action rows must be wrapping flexes with no
    grid_template_columns left in them."""
    for name, fn in (
        ("render_concept_template", reckonings.render_concept_template),
        ("render_comment", reckonings.render_comment),
    ):
        src = inspect.getsource(fn)
        assert "grid_template_columns=" not in src, (
            f"{name} still lays its action row out on a fixed grid"
        )
        assert 'wrap="wrap"' in src, f"{name} action row does not wrap"

    # The comments page's parent row carries the feedback button and lives in
    # the comments view function; find it by its detract wiring.
    parent_src = inspect.getsource(reckonings)
    assert 'grid_template_columns="1fr 1fr 11fr' not in parent_src, (
        "the comments-page parent action row is still a fixed grid"
    )


def test_login_gate_is_signup_first():
    """Anonymous write attempts must go to /signup, not /login (client
    request: Prolific testers are mostly new users).

    Returning users who try an existing email on /signup get bounced to
    /login with their ?next path preserved, so the old "User with that
    email already exists" dead-end cannot recur.
    """
    src = inspect.getsource(reckonings.ReckoningsPageState._require_login_redirect)
    assert "/signup?next=" in src
    group_src = inspect.getsource(
        GroupPageState._require_login_redirect_for_submission
    )
    assert "/signup?next=" in group_src
    auth_src = inspect.getsource(auth_state.AuthState)
    assert "rx.redirect(self.login_link)" in auth_src, (
        "signup duplicate-email must bounce to /login, not dead-end"
    )
