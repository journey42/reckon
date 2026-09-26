"""Convener comment-hiding.

The group convener can hide a comment without deleting it — useful while a
group is forming and there are no popular comments to crowd out weird or
crude posting. The record is kept; non-conveners see "Hidden by group
convener" instead of the content. Group contents were already private to
the group; this only gates visibility *within* the group.
"""

from datetime import datetime, timezone
from typing import Optional

from rhiz.state.base import Group, Log, Reckoning


def can_moderate(user, group: Optional[Group]) -> bool:
    """True if this user may hide/unhide comments in this group.

    The group convener (creator) or any admin.
    """
    if user is None or group is None:
        return False
    if user.role >= 2:
        return True
    return group.created_by == user.id


def hide_comment(session, comment_id: int, by_user) -> bool:
    """Hide a comment. Returns True if the caller was allowed and it changed."""
    comment = session.get(Reckoning, comment_id)
    if comment is None or comment.group_id is None:
        return False
    group = session.get(Group, comment.group_id)
    if not can_moderate(by_user, group):
        return False
    comment.hidden_by_convener = True
    comment.hidden_by = by_user.id
    comment.hidden_at = datetime.now(timezone.utc)
    session.add(comment)
    session.add(
        Log(
            user_id=by_user.id,
            content=f"hid comment {comment_id} in group {comment.group_id}",
            type="group_moderation",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    return True


def unhide_comment(session, comment_id: int, by_user) -> bool:
    """Unhide a previously hidden comment. Returns True if allowed+changed."""
    comment = session.get(Reckoning, comment_id)
    if comment is None:
        return False
    group = session.get(Group, comment.group_id) if comment.group_id else None
    if not can_moderate(by_user, group):
        return False
    comment.hidden_by_convener = False
    comment.hidden_by = None
    comment.hidden_at = None
    session.add(comment)
    session.commit()
    return True
