from dataclasses import dataclass
from rhiz.utils.permissions import can_manage_debates


@dataclass
class FakeUser:
    role: int


def test_admin_can_manage():
    assert can_manage_debates(FakeUser(role=2)) is True


def test_moderator_cannot_by_default():
    assert can_manage_debates(FakeUser(role=1)) is False


def test_regular_cannot():
    assert can_manage_debates(FakeUser(role=0)) is False


def test_none_user_cannot():
    assert can_manage_debates(None) is False
