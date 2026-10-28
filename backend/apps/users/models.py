from django.db import models

class UserProfile(models.Model):
    username = models.CharField(max_length=50, unique=True, null=True, blank=True)
    password = models.CharField(max_length=128, default='10')
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    avatar_url = models.URLField(blank=True, default='')
    # UPI id (VPA) for settle-up links. Kept out of the user list on purpose: it's only
    # served from /api/users/<id>/upi/, when someone is about to pay this person.
    upi_id = models.CharField(max_length=100, blank=True, default='')
    
    # Blinkit Session Fields (Stored per user in DB)
    blinkit_access_token = models.TextField(blank=True, null=True)
    blinkit_auth_key = models.CharField(max_length=255, blank=True, null=True)
    blinkit_device_id = models.CharField(max_length=255, blank=True, null=True)
    blinkit_session_uuid = models.CharField(max_length=255, blank=True, null=True)
    
    # Swiggy MCP Session Fields (Stored per user in DB)
    swiggy_access_token = models.TextField(blank=True, null=True)
    swiggy_refresh_token = models.TextField(blank=True, null=True)
    # When the access token dies. Swiggy can't refresh an already-expired token, so the
    # refresh has to happen before this, which means knowing it rather than finding out
    # from a 401. Also what the UI's "session expired" state is derived from: the old
    # in-memory flag was invisible to the other gunicorn workers.
    swiggy_token_expires_at = models.DateTimeField(blank=True, null=True)
    # PKCE verifier for the login in flight. In the DB, not in memory, because the
    # /auth_url and /callback requests can land on different gunicorn workers.
    swiggy_pkce_verifier = models.CharField(max_length=128, blank=True, null=True)
    # Random nonce for the login in flight, sent as the OAuth `state` and checked on the
    # way back. It's what identifies the user at the callback now that the redirect URI
    # has to be one constant string.
    swiggy_oauth_state = models.CharField(max_length=64, blank=True, null=True)
    # The exact redirect_uri sent to /auth/authorize, replayed verbatim at token
    # exchange. Rebuilding it there would risk a different string (the two hops can
    # arrive on different hostnames) and Swiggy matches it exactly.
    swiggy_oauth_redirect_uri = models.CharField(max_length=300, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (@{self.username or self.id})"
