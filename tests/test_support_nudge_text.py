"""The guidance a submitter sees right after posting a concept.

This banner is the first thing someone reads after submitting, and it is the
place they are told their idea is not public yet and what to do about it. It has
already shipped once with a typo that turned the second option into two
sunglasses emoji — "A) ... and then 😎 😎" — so the letters are pinned here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rhiz.pages.reckonings import (  # noqa: E402
    NUDGE_COLLAPSED_SUMMARY,
    NUDGE_FIRST_TOPIC_BODY,
    NUDGE_HEADING,
    NUDGE_RELATED_BODY,
)


def test_the_two_options_are_lettered_a_and_b():
    assert "A) Upvote your own submission" in NUDGE_RELATED_BODY
    assert "B) Lend your vote to the previous entry" in NUDGE_RELATED_BODY


def test_no_emoji_stands_in_for_a_letter():
    """The regression the client reported: sunglasses where 'B)' should be."""
    emoji = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]")
    for name, text in (
        ("NUDGE_RELATED_BODY", NUDGE_RELATED_BODY),
        ("NUDGE_FIRST_TOPIC_BODY", NUDGE_FIRST_TOPIC_BODY),
        ("NUDGE_COLLAPSED_SUMMARY", NUDGE_COLLAPSED_SUMMARY),
        ("NUDGE_HEADING", NUDGE_HEADING),
    ):
        found = emoji.findall(text)
        assert not found, f"{name} contains emoji that may be standing in for text: {found}"


def test_the_banner_still_says_the_thing_is_private():
    """Wording can be tidied; this promise cannot be lost."""
    assert "not been published" in NUDGE_HEADING.lower()
    assert "Nothing is public" in NUDGE_RELATED_BODY
    assert "not be public" in NUDGE_FIRST_TOPIC_BODY


def test_each_option_sits_on_its_own_line():
    lines = NUDGE_RELATED_BODY.splitlines()
    assert sum(1 for line in lines if re.match(r"^[AB]\)", line)) == 2, lines
