"""Feed row actions must stay reachable.

Comment entry points silently disappeared from feed concept rows during the
July group-feed rework: the buttons existed only on the /comments/<id> detail
page, so users in a group could vote on a concept but had no way to comment on
it, and the site recorded zero comments for two months without any error
anywhere. These tests pin the invariants that would have caught it.
"""

import inspect

from rhiz.pages import reckonings


def test_feed_concept_rows_offer_comment_buttons():
    src = inspect.getsource(reckonings.render_concept_template)
    for button in (
        "support_comment_button",
        "poo_comment_button",
        "detract_from_comment_button",
    ):
        assert button in src, f"{button} missing from feed rows"


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


def test_login_gate_is_login_first():
    """Anonymous write attempts must go to /login, not /signup.

    Sending returning users to /signup made "User with that email already
    exists" look like "I was unable to make an account".
    """
    src = inspect.getsource(reckonings.ReckoningsPageState._require_login_redirect)
    assert "/login?next=" in src
    assert "/signup?next=" not in src
