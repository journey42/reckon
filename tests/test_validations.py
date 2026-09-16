"""Input validation policy tests.

The password rule was deliberately simplified: it used to demand an uppercase
letter, a digit and a symbol from a fixed set, surfaced as blocking browser
popups. That produced memorable-but-annoying failures ("Test@1234" style
passwords people could not recall) and signup reports that read as "broken".
The policy is now length plus a small common-password blocklist, per
NIST SP 800-63B, with the requirement shown inline before submit.
"""

import pytest

from rhiz.utils.validations import (
    COMMON_PASSWORDS,
    PASSWORD_MIN_LENGTH,
    password_hint,
    validate_email,
    validate_password,
    validate_username,
)


def test_passphrase_without_complexity_is_accepted():
    ok, _ = validate_password("quiet harbor lights")
    assert ok is True


def test_lowercase_only_and_symbols_only_are_both_fine():
    assert validate_password("all lowercase words here")[0] is True
    assert validate_password("!!!!good-long-one")[0] is True


def test_short_password_rejected():
    ok, msg = validate_password("a" * (PASSWORD_MIN_LENGTH - 1))
    assert ok is False
    assert str(PASSWORD_MIN_LENGTH) in msg


def test_exact_minimum_length_accepted():
    # Careful: "1"*8 and "abcdefgh" are both on the common-password list.
    candidate = "qz" * (PASSWORD_MIN_LENGTH // 2)
    assert len(candidate) == PASSWORD_MIN_LENGTH
    assert candidate not in COMMON_PASSWORDS
    assert validate_password(candidate)[0] is True


@pytest.mark.parametrize("weak", ["password1", "12345678", "Password123", "letmein1"])
def test_common_passwords_rejected(weak):
    assert weak.lower() in COMMON_PASSWORDS
    ok, msg = validate_password(weak)
    assert ok is False
    assert "common" in msg.lower()


def test_blocklist_is_matched_case_insensitively_and_padded():
    assert validate_password("  PASSWORD1  ")[0] is False


def test_empty_and_none_rejected():
    assert validate_password("")[0] is False
    assert validate_password(None)[0] is False


def test_hint_states_the_actual_rule():
    hint = password_hint()
    assert str(PASSWORD_MIN_LENGTH) in hint
    # The hint must not reintroduce rules that no longer exist.
    for gone in ("uppercase", "lowercase", "special character", "number"):
        assert gone not in hint.lower()


def test_hint_is_short():
    assert len(password_hint()) < 120


def test_email_still_validated():
    assert validate_email("someone@example.org")[0] is True
    assert validate_email("not-an-email")[0] is False


def test_username_rules_unchanged():
    assert validate_username("Delilah")[0] is True
    assert validate_username("has space")[0] is False
