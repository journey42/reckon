"""Verification-token helpers for group-origin signups."""

import string

from rhiz.utils.verification import generate_token, is_group_origin, TOKEN_TTL_HOURS


def test_generate_token_is_urlsafe_and_unique():
    t1, t2 = generate_token(), generate_token()
    assert t1 != t2
    assert len(t1) >= 32
    allowed = set(string.ascii_letters + string.digits + "-_")
    assert set(t1) <= allowed


def test_is_group_origin():
    assert is_group_origin("/group/housing") is True
    assert is_group_origin("/group/") is True
    assert is_group_origin("/your_drafts") is False
    assert is_group_origin(None) is False
    assert is_group_origin("") is False


def test_room_links_are_not_group_origin():
    # A live Q&A room link must not be treated as a group-affinity signup:
    # rooms are anonymous and never create memberships.
    assert is_group_origin("/room/abc123") is False


def test_group_root_is_not_group_origin():
    # "/group" without a slug carries no group to connect to.
    assert is_group_origin("/group") is False


def test_ttl_constant():
    assert TOKEN_TTL_HOURS == 72
