"""Role-gated permissions for debate management.

DEBATE_CREATE_MIN_ROLE is the minimum role allowed to create/manage debates.
Defaults to admin; lower it (1 = moderator, 0 = any user) via the env var to
progressively open the feature up.
"""

import os
from rhiz.state.base import UserTypes


def _min_role() -> int:
    try:
        return int(os.getenv("DEBATE_CREATE_MIN_ROLE", str(UserTypes.admin)))
    except ValueError:
        return UserTypes.admin


DEBATE_CREATE_MIN_ROLE = _min_role()


def can_manage_debates(user) -> bool:
    """True if the user exists and meets the minimum role threshold."""
    return user is not None and getattr(user, "role", -1) >= DEBATE_CREATE_MIN_ROLE
