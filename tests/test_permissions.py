"""Group-management permission policy.

Access is granted per user via the ``can_create_groups`` flag (set by an admin
on the Users page); role alone is not sufficient. Live Q&A rooms deliberately
bypass this check so any account holder can ask a question — see
``tests/test_rooms.py``.
"""

from dataclasses import dataclass

from rhiz.utils.permissions import can_manage_groups


@dataclass
class FakeUser:
    role: int
    can_create_groups: bool = False


def test_flagged_user_can_manage():
    assert can_manage_groups(FakeUser(role=0, can_create_groups=True)) is True


def test_admin_without_flag_cannot_manage_by_role_alone():
    # Role is irrelevant: an admin who has not been granted the flag is refused.
    assert can_manage_groups(FakeUser(role=2, can_create_groups=False)) is False


def test_regular_user_without_flag_cannot():
    assert can_manage_groups(FakeUser(role=0, can_create_groups=False)) is False


def test_moderator_without_flag_cannot():
    assert can_manage_groups(FakeUser(role=1, can_create_groups=False)) is False


def test_none_user_cannot():
    assert can_manage_groups(None) is False


def test_user_object_missing_the_flag_is_denied():
    # Defensive: an object without the attribute at all must not slip through.

    class Legacy:
        role = 2

    assert can_manage_groups(Legacy()) is False
