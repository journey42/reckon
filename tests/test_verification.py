import string
from rhiz.utils.verification import generate_token, is_debate_origin, TOKEN_TTL_HOURS


def test_generate_token_is_urlsafe_and_unique():
    t1, t2 = generate_token(), generate_token()
    assert t1 != t2
    assert len(t1) >= 32
    allowed = set(string.ascii_letters + string.digits + "-_")
    assert set(t1) <= allowed


def test_is_debate_origin():
    assert is_debate_origin("/debate/housing") is True
    assert is_debate_origin("/debate/") is True
    assert is_debate_origin("/your_drafts") is False
    assert is_debate_origin(None) is False
    assert is_debate_origin("") is False


def test_ttl_constant():
    assert TOKEN_TTL_HOURS == 72
