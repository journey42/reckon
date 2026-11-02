"""The Substack link at the bottom of the demo page.

Small and easy to lose in a refactor of the page layout, so it is pinned here:
the client's link, on the page it belongs to, opened safely.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rhiz.pages import demo  # noqa: E402


def _rendered() -> str:
    return json.dumps(demo._substack_footer().render())


def test_the_client_link_is_the_one_on_the_page():
    assert demo.SUBSTACK_URL == "https://americaantonym.substack.com"
    assert demo.SUBSTACK_URL in _rendered()
    # https, not http: the page is served over TLS and a downgrade would warn.
    assert demo.SUBSTACK_URL.startswith("https://")


def test_it_opens_in_a_new_tab_without_handing_over_opener():
    """A click mid-answer must not lose the page, and the opened tab must not be
    able to reach back through ``window.opener``."""
    rendered = _rendered()
    assert "_blank" in rendered
    assert "noopener" in rendered
    assert "noreferrer" in rendered


def test_the_footer_is_on_the_page_in_both_states():
    """It sits outside the question/no-question branches, so it is also present
    on the day nothing is set up."""
    # default=str: the page tree carries Vars, which JSON cannot encode
    page = json.dumps(demo.demo_page().render(), default=str)
    assert demo.SUBSTACK_URL in page
    # exactly once: a second copy would mean it got added to a branch as well
    assert page.count(demo.SUBSTACK_URL) == 1
