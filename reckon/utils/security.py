"""Password hashing utilities."""

from __future__ import annotations

import bcrypt


def _coerce_bytes(value: str | bytes | None) -> bytes:
    if isinstance(value, bytes):
        return value
    return (value or "").encode("utf-8")


def is_hashed(value: str | None) -> bool:
    """Return True if the stored password looks like a bcrypt hash."""
    if not value:
        return False
    return value.startswith("$2")


def hash_password(plain_text: str) -> str:
    """Hash a plaintext password using bcrypt."""
    password_bytes = _coerce_bytes(plain_text)
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_text: str, stored_value: str | None) -> tuple[bool, bool]:
    """Verify a password and indicate if the stored value should be upgraded.

    Returns:
        (is_valid, needs_rehash)
    """
    if not stored_value:
        return False, False

    password_bytes = _coerce_bytes(plain_text)
    stored_text = stored_value or ""

    if is_hashed(stored_text):
        try:
            return bcrypt.checkpw(password_bytes, stored_text.encode("utf-8")), False
        except ValueError:
            return False, False

    # Fallback for legacy plain text passwords.
    return stored_text == plain_text, True
