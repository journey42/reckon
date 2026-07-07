"""Permissions for group management.

Only users with can_create_groups=True (set by an admin on the Users page)
can create and manage groups.
"""


def can_manage_groups(user) -> bool:
    """True if the user has been individually granted group access."""
    return user is not None and getattr(user, "can_create_groups", False)
