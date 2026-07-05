"""Role-gated permissions for group management.

GROUP_CREATE_MIN_ROLE is the minimum role allowed to create/manage groups.
Defaults to admin; lower it (1 = moderator, 0 = any user) via the env var to
progressively open the feature up.
"""

import os
from rhiz.state.base import UserTypes


def _min_role() -> int:
    try:
        return int(os.getenv("GROUP_CREATE_MIN_ROLE", str(UserTypes.admin)))
    except ValueError:
        return UserTypes.admin


GROUP_CREATE_MIN_ROLE = _min_role()


def can_manage_groups(user) -> bool:
    """True if the user exists and either meets the minimum role threshold or
    has been individually granted group access (per-user flag set by an admin
    on the Users page)."""
    return user is not None and (
        getattr(user, "role", -1) >= GROUP_CREATE_MIN_ROLE
        or getattr(user, "can_create_groups", False)
    )
