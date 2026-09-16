"""validations for common user inputs."""

import re


def validate_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if re.match(pattern, email):
        return True, "Email is valid."
    return False, "Email is invalid."


foul_words = {"shit", "fuck", "tits", "balls"}  # Add your list of foul words


def validate_username(username):
    if any(foul_word in username.lower() for foul_word in foul_words):
        return False, "Username contains inappropriate language."
    if not username.isalnum():
        return False, "Username must contain only letters and numbers."
    return True, "Username is valid."


PASSWORD_MIN_LENGTH = 8

# A short list of the passwords nobody should be able to pick. Deliberately
# tiny: the old policy demanded an uppercase letter, a digit and a symbol from
# a fixed set, which produced "Test@1234"-style passwords people could not
# remember and a signup flow that felt broken. Length plus this blocklist is
# what NIST SP 800-63B actually recommends; composition rules are discouraged.
COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "passw0rd",
    "qwertyuiop",
    "qwerty123",
    "12345678",
    "123456789",
    "1234567890",
    "11111111",
    "00000000",
    "abcdefgh",
    "iloveyou",
    "letmein1",
    "welcome1",
    "admin123",
}


def validate_password(password):
    """Accept any password of PASSWORD_MIN_LENGTH or more that is not one of
    the handful of catastrophically common choices. Spaces are allowed so
    passphrases work."""
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Please use at least {PASSWORD_MIN_LENGTH} characters."
    if password.strip().lower() in COMMON_PASSWORDS:
        return False, "That password is too common — please choose another."
    return True, "Password is good."


def password_hint() -> str:
    """One-line guidance to show beside a password field, so people know the
    rule before they hit submit rather than via a popup afterwards."""
    return f"At least {PASSWORD_MIN_LENGTH} characters. Any combination, spaces welcome — pick something memorable."


def validate_role(role):
    if role not in {0, 1, 2}:
        return (
            False,
            "Role must be either 'user (0)' or 'moderator (1)' or 'admin (2)'.",
        )
    return True, "Role is valid."
