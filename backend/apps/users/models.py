from django.db import models

class UserProfile(models.Model):
    username = models.CharField(max_length=50, unique=True, null=True, blank=True)
    password = models.CharField(max_length=128, default='10')
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    avatar_url = models.URLField(blank=True, default='')
    
    # Blinkit Session Fields (Stored per user in DB)
    blinkit_access_token = models.TextField(blank=True, null=True)
    blinkit_auth_key = models.CharField(max_length=255, blank=True, null=True)
    blinkit_device_id = models.CharField(max_length=255, blank=True, null=True)
    blinkit_session_uuid = models.CharField(max_length=255, blank=True, null=True)
    
    # Swiggy MCP Session Fields (Stored per user in DB)
    swiggy_access_token = models.TextField(blank=True, null=True)
    swiggy_refresh_token = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (@{self.username or self.id})"
