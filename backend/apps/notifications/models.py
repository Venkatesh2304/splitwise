from django.db import models
from apps.users.models import UserProfile

class PushSubscription(models.Model):
    """One browser/device that has allowed notifications. The endpoint identifies the
    device, so re-subscribing it under another user moves it (shared phone, switch user)."""
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.CharField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Push device for {self.user.name} ({self.user_agent[:40]})"

class ActivityEvent(models.Model):
    """One change in a group, kept so people can see what happened while they were away.

    `lines` holds the sentence each person should read, keyed by their user id — the very
    text their notification carried. That keeps the two in step, and its keys are exactly
    the people the change concerned (everyone involved except whoever made it), so
    counting what someone hasn't seen is a lookup rather than a re-derivation.
    """
    EXPENSE_ADDED = 'expense_added'
    EXPENSE_EDITED = 'expense_edited'
    EXPENSE_DELETED = 'expense_deleted'
    SETTLEMENT_RECORDED = 'settlement_recorded'
    SETTLEMENT_DELETED = 'settlement_deleted'
    NUDGED = 'nudged'

    group = models.ForeignKey('groups.Group', on_delete=models.CASCADE, related_name='activity')
    actor = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity')
    kind = models.CharField(max_length=30)
    # Not a ForeignKey: a deletion event has to outlive the expense it describes
    expense_id = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=300)
    url = models.CharField(max_length=300, blank=True, default='')
    lines = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['group', '-created_at'])]

    def line_for(self, user_id):
        return self.lines.get(str(user_id), '')

    def concerns(self, user_id):
        return str(user_id) in self.lines

    def __str__(self):
        return f"[{self.kind}] {self.title}"
