"""Reading the activity log: what a person hasn't seen in a group yet.

"Not seen" means: recorded after they last opened the group, by someone else, and
concerning them. Whether it concerns them is already decided by the notification's
recipient rules, which are what `ActivityEvent.lines` is keyed on.
"""
from django.utils import timezone

from apps.groups.models import GroupMember

from .models import ActivityEvent

RECENT_LIMIT = 50


def baseline_for(group_id, user_id):
    """When this person last looked. Never looked → when they joined, so a new member
    doesn't open the app to a backlog of things that happened before they existed."""
    member = GroupMember.objects.filter(group_id=group_id, user_id=user_id).first()
    if member is None:
        return None
    return member.last_seen_at or member.joined_at


def mark_seen(group_id, user_id):
    """Returns the previous baseline, so the caller can still show what was new."""
    member = GroupMember.objects.filter(group_id=group_id, user_id=user_id).first()
    if member is None:
        return None
    previous = member.last_seen_at or member.joined_at
    member.last_seen_at = timezone.now()
    member.save(update_fields=['last_seen_at'])
    return previous


def for_user(group_id, user_id, since=None, limit=RECENT_LIMIT):
    events = ActivityEvent.objects.filter(group_id=group_id, lines__has_key=str(user_id))
    if since is not None:
        events = events.filter(created_at__gt=since)
    return list(events.select_related('actor')[:limit])


def unseen_count(group_id, user_id):
    baseline = baseline_for(group_id, user_id)
    if baseline is None:
        return 0
    return ActivityEvent.objects.filter(
        group_id=group_id, lines__has_key=str(user_id), created_at__gt=baseline
    ).count()


def serialize(events, user_id):
    return [
        {
            "id": event.id,
            "kind": event.kind,
            "title": event.title,
            "line": event.line_for(user_id),
            "actor": event.actor.name if event.actor else None,
            "expense_id": event.expense_id,
            "url": event.url,
            "created_at": event.created_at,
        }
        for event in events
    ]
