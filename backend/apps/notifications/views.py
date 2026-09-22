from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import keys, push
from .events import resolve_actor
from .models import PushSubscription

NOT_SET_UP = {"error": "Notifications are not set up on the server yet (run manage.py ensure_vapid_keys)."}

@api_view(['GET'])
def push_public_key(request):
    vapid_keys = keys.load()
    if vapid_keys is None:
        return Response(NOT_SET_UP, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"public_key": vapid_keys.public_key})

@api_view(['POST'])
def push_subscribe(request):
    user = resolve_actor(request.data.get("user_id"))
    subscription = request.data.get("subscription") or {}
    endpoint = str(subscription.get("endpoint") or "")
    sub_keys = subscription.get("keys") or {}
    if not user:
        return Response({"error": "Unknown user."}, status=status.HTTP_400_BAD_REQUEST)
    if not endpoint.startswith("https://") or not sub_keys.get("p256dh") or not sub_keys.get("auth"):
        return Response({"error": "Invalid push subscription."}, status=status.HTTP_400_BAD_REQUEST)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": user,
            "p256dh": sub_keys["p256dh"],
            "auth": sub_keys["auth"],
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
        },
    )
    return Response({"ok": True, "devices": PushSubscription.objects.filter(user=user).count()})

@api_view(['POST'])
def push_unsubscribe(request):
    endpoint = str(request.data.get("endpoint") or "")
    deleted, _ = PushSubscription.objects.filter(endpoint=endpoint).delete()
    return Response({"ok": True, "removed": deleted})

@api_view(['POST'])
def push_test(request):
    vapid_keys = keys.load()
    if vapid_keys is None:
        return Response(NOT_SET_UP, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    user = resolve_actor(request.data.get("user_id"))
    if not user:
        return Response({"error": "Unknown user."}, status=status.HTTP_400_BAD_REQUEST)

    payload = {
        "title": "Notifications are on ✅",
        "body": "You'll hear when someone adds, edits or deletes an expense you're in, or settles up with you.",
        "tag": "test",
        "url": "/",
    }
    devices = list(PushSubscription.objects.filter(user=user))
    sent = sum(push.send(sub, payload, vapid_keys) for sub in devices)
    return Response({"sent": sent, "devices": len(devices)})
