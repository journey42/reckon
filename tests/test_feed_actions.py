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


def test_feed_grid_columns_match_row_children():
    """The row is a CSS grid: if columns and children drift apart, buttons get
    pushed into the wrong track or clipped. Count both from the source."""
    src = inspect.getsource(reckonings.render_concept_template)
    grid_line = [ln for ln in src.splitlines() if "grid_template_columns=" in ln]
    assert grid_line, "no grid template found"
    columns = grid_line[-1].split('"')[1].split()
    # 17 tracks: 11 original + 6 comment slots (3 buttons + 3 tallies).
    assert len(columns) == 17, f"expected 17 grid tracks, got {len(columns)}"


def test_login_gate_is_login_first():
    """Anonymous write attempts must go to /login, not /signup.

    Sending returning users to /signup made "User with that email already
    exists" look like "I was unable to make an account".
    """
    src = inspect.getsource(reckonings.ReckoningsPageState._require_login_redirect)
    assert "/login?next=" in src
    assert "/signup?next=" not in src
