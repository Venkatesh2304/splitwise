"""Delivers web pushes to every device a user has subscribed.

Sending happens after the database commit on a small thread pool, so an API response
never waits on the push service. A 404/410 means the browser dropped the subscription
(uninstalled, permission revoked), so the row is deleted.
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from pywebpush import WebPushException, webpush

from . import keys
from .models import PushSubscription

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="push")
GONE = {404, 410}
TTL_SECONDS = 24 * 60 * 60

def send(sub, payload, vapid_keys):
    """Send one payload to one device. Returns True when the push service accepted it."""
    try:
        webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=json.dumps(payload),
            vapid_private_key=vapid_keys.vapid,
            # A fresh dict every call: webpush fills in "aud" from the endpoint and would
            # otherwise reuse Google's audience for an Apple endpoint.
            vapid_claims={"sub": vapid_keys.subject},
            ttl=TTL_SECONDS,
            headers={"Urgency": "high"},
            timeout=10,
        )
    except WebPushException as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code in GONE:
            PushSubscription.objects.filter(pk=sub.pk).delete()
        else:
            logger.warning("Push to %s failed (%s): %s", sub.user_id, status_code, exc)
        return False
    except Exception:
        logger.exception("Push to %s failed", sub.user_id)
        return False
    PushSubscription.objects.filter(pk=sub.pk).update(last_success_at=timezone.now())
    return True

def deliver(messages):
    """messages: list of (user_id, payload). Sends to all of each user's devices."""
    vapid_keys = keys.load()
    if vapid_keys is None:
        return 0
    sent = 0
    for user_id, payload in messages:
        for sub in PushSubscription.objects.filter(user_id=user_id):
            sent += send(sub, payload, vapid_keys)
    return sent

def _deliver_in_thread(messages):
    try:
        deliver(messages)
    finally:
        connection.close()

def queue(messages):
    """Send after the current transaction commits, without blocking the request."""
    if not messages:
        return
    if getattr(settings, "PUSH_SEND_INLINE", False):
        transaction.on_commit(lambda: deliver(messages))
    else:
        transaction.on_commit(lambda: _executor.submit(_deliver_in_thread, messages))
