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
