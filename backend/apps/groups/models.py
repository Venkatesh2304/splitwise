from django.db import models
from apps.users.models import UserProfile

class GroupCategory(models.TextChoices):
    TRIP = 'TRIP', 'Trip'
    HOME = 'HOME', 'Home'
    EVENT = 'EVENT', 'Event'
    OTHER = 'OTHER', 'Other'

class Group(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=20, choices=GroupCategory.choices, default=GroupCategory.TRIP)
    currency = models.CharField(max_length=10, default='$')
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(UserProfile, through='GroupMember', related_name='user_groups')

    def __str__(self):
        return f"{self.name} ({self.category})"

class GroupMember(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')

    def __str__(self):
        return f"{self.user.name} in {self.group.name}"
