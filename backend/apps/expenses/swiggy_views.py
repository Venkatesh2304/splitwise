import requests
import json
import os
import time
import base64
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlsplit, urlunsplit
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.db.models import Q
from apps.users.models import UserProfile
from apps.expenses.models import Expense
from apps.expenses.grocery_engine import GrocerySplitEngine
from apps.expenses.grocery_engine.split_engine import order_expense_query
from apps.expenses.grocery_engine.state import (
    get_swiggy_order_cache,
    get_swiggy_food_order_cache,
    CACHE_TTL_SECONDS
)
from apps.expenses.grocery_engine.order_store import OrderStoreManager, _sort_orders_descending
from apps.expenses.blinkit_views import get_user_profile_by_req

MCP_BASE = "https://mcp.swiggy.com"

# Swiggy's OAuth client is public (PKCE, no secret). Overridable in case we register
# our own; the callback below is what turns reconnect into one click instead of the
# copy-the-localhost-URL workaround.
SWIGGY_CLIENT_ID = os.environ.get("SWIGGY_CLIENT_ID", "swiggy-mcp")
SWIGGY_PUBLIC_CALLBACK = os.environ.get("SWIGGY_PUBLIC_CALLBACK", "").strip()
# Where to send the browser once login finishes. Derived from the request when unset.
SWIGGY_APP_ROOT = os.environ.get("SWIGGY_APP_ROOT", "").strip()

# Swiggy runs one MCP server per vertical. The vertical is the path, not a field in the
# payload, so Instamart and food are two separate calls.
IM_PATH = "/im"
FOOD_PATH = "/food"

# Stored on GroceryOrderRecord.platform. models.py derives order_type from it.
INSTAMART_PLATFORM = "INSTAMART"
FOOD_PLATFORM = "SWIGGY_FOOD"

# Up to 15 per call and no pagination (Swiggy's cap). Saved orders are never deleted,
# so history still accumulates across refreshes.
FOOD_ORDER_COUNT = 15

# What goes into an expense's notes["platform"]. Kept human-readable because the
# frontend and derive_order_title already match on these strings.
SWIGGY_PLATFORM_LABELS = {
    INSTAMART_PLATFORM: "Swiggy Instamart",
    FOOD_PLATFORM: "Swiggy Food",
}


def swiggy_platform_label(order_type):
    return SWIGGY_PLATFORM_LABELS.get(str(order_type or "").upper(), "Swiggy Instamart")


class SwiggyAuthExpired(Exception):
    """The access token is dead and the refresh token could not revive it."""


class SwiggyRateLimited(Exception):
    """Swiggy asked us to slow down. Carries the Retry-After it gave us, in seconds."""

    def __init__(self, retry_after=None):
        super().__init__(f"Swiggy rate limited (retry after {retry_after}s)")
        self.retry_after = retry_after


def _jwt_claims(token):
    """The payload of a JWT, without verifying it.

    Only ever used on tokens Swiggy issued to us and we stored ourselves, to read
    `exp` — so there is nothing to verify and no need for a JWT library.
    """
    try:
        payload = str(token).split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None


def swiggy_token_expiry(token):
    """When this access token dies, as an aware datetime, or None if that's unknowable.

    None means "no idea", never "expired": the MANUAL_JSON_OVERRIDE sentinel and any
    non-JWT token have to keep counting as usable.
    """
    if not token or token == "MANUAL_JSON_OVERRIDE":
        return None
    claims = _jwt_claims(token) or {}
    exp = claims.get("exp")
    try:
        return datetime.fromtimestamp(float(exp), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def swiggy_expires_at(user_profile):
    """The stored expiry, falling back to the token's own `exp` for older rows."""
    return user_profile.swiggy_token_expires_at or swiggy_token_expiry(user_profile.swiggy_access_token)


# Refresh this far ahead of expiry. Swiggy cannot refresh an already-dead token, so the
# margin has to cover the gap between scheduled runs plus any clock skew.
REFRESH_MARGIN = timedelta(minutes=10)


def store_swiggy_tokens(user_profile, data, save=True):
    """Record a token response. Returns the new access token, or None.

    `expires_in` is what Swiggy documents; the token's own `exp` is the fallback.
    """
    access = data.get("access_token")
    if not access:
        return None

    user_profile.swiggy_access_token = access
    # Swiggy rotates the refresh token on every refresh; keep the old one if it doesn't.
    user_profile.swiggy_refresh_token = data.get("refresh_token") or user_profile.swiggy_refresh_token

    expires_at = None
    try:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=float(data["expires_in"]))
    except (KeyError, TypeError, ValueError):
        expires_at = swiggy_token_expiry(access)
    user_profile.swiggy_token_expires_at = expires_at

    if save:
        user_profile.save()
    return access


def clear_swiggy_session(user_profile, save=True):
    """Forget the session and anything about a login in flight."""
    user_profile.swiggy_access_token = None
    user_profile.swiggy_refresh_token = None
    user_profile.swiggy_token_expires_at = None
    user_profile.swiggy_pkce_verifier = None
    user_profile.swiggy_oauth_state = None
    user_profile.swiggy_oauth_redirect_uri = None
    if save:
        user_profile.save()


def refresh_swiggy_token(user_profile):
    """Swap the refresh token for a new pair. Returns the new access token, or None.

    Swiggy wants this as JSON, not form-encoded. A dead refresh token comes back as
    `invalid_grant`, which their docs say not to retry — so the session is cleared and
    the user is asked to reconnect instead of us hammering a token that can't work.
    """
    if not user_profile.swiggy_refresh_token:
        return None
    try:
        res = requests.post(
            f"{MCP_BASE}/auth/token",
            json={
                "grant_type": "refresh_token",
                "refresh_token": user_profile.swiggy_refresh_token,
                "client_id": SWIGGY_CLIENT_ID,
            },
            timeout=10.0,
        )
        if res.status_code == 200:
            new_access = store_swiggy_tokens(user_profile, res.json())
            if new_access:
                return new_access

        error = ""
        try:
            error = (res.json() or {}).get("error", "")
        except Exception:
            pass
        if error == "invalid_grant":
            print(f"Swiggy refresh token is dead for {user_profile.name}; reconnect needed.")
            clear_swiggy_session(user_profile)
        else:
            print(f"Swiggy token refresh failed for {user_profile.name}: HTTP {res.status_code} {error}")
    except Exception as e:
        print(f"Swiggy token refresh error for {user_profile.name}: {e}")
    return None


def swiggy_session_state(user_profile):
    """What the UI needs to know about the session, derived from the stored token.

    Derived rather than remembered: the old auth_error flag lived in a per-process
    dict, so with three gunicorn workers the request that noticed the expiry was
    usually not the request that reported it.
    """
    token = user_profile.swiggy_access_token
    manual = token == "MANUAL_JSON_OVERRIDE"
    expires_at = None if manual else swiggy_expires_at(user_profile)
    now = datetime.now(timezone.utc)

    # An unknown expiry is not an expired one.
    is_expired = bool(expires_at and expires_at <= now)
    stale = bool(expires_at and expires_at - now <= REFRESH_MARGIN)
    flagged = bool(get_swiggy_order_cache(user_profile.phone_number).get("auth_error"))

    return {
        "is_logged_in": bool(token) and not is_expired,
        "needs_reconnect": bool(token) and (stale or flagged),
        "manual_override": manual,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


def swiggy_mcp_call(user_profile, path, tool, arguments=None, timeout=15.0):
    """Call one MCP tool, refreshing the token once if it has expired.

    Raises SwiggyAuthExpired when the session is dead and cannot be revived, so callers
    can prompt for a reconnect instead of silently serving stale orders.
    """
    token = user_profile.swiggy_access_token
    if not token or token == "MANUAL_JSON_OVERRIDE":
        raise SwiggyAuthExpired("No Swiggy session")

    # Refresh ahead of expiry rather than after a 401: Swiggy cannot refresh a token
    # that has already died, so waiting for the rejection is waiting too long.
    expires_at = swiggy_expires_at(user_profile)
    if expires_at and expires_at - datetime.now(timezone.utc) <= REFRESH_MARGIN:
        if not refresh_swiggy_token(user_profile) and expires_at <= datetime.now(timezone.utc):
            raise SwiggyAuthExpired("Swiggy session expired and could not be refreshed")

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }

    for attempt in (1, 2):
        headers = {
            "Authorization": f"Bearer {user_profile.swiggy_access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        res = requests.post(f"{MCP_BASE}{path}", json=payload, headers=headers, timeout=timeout)

        if res.status_code == 200:
            body = _decode_mcp_body(res)
            err_code = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
            # A dead session can also come back as a JSON-RPC error rather than a 401.
            if err_code == -32001 and attempt == 1 and refresh_swiggy_token(user_profile):
                continue
            if err_code == -32001:
                raise SwiggyAuthExpired("Swiggy session expired")
            # Likewise a rate limit, which Swiggy surfaces as -32000 at the MCP layer.
            if err_code == -32000:
                raise SwiggyRateLimited(_retry_after_seconds(res))
            return body

        if res.status_code in (401, 403):
            if attempt == 1 and refresh_swiggy_token(user_profile):
                continue
            raise SwiggyAuthExpired(f"Swiggy session expired (HTTP {res.status_code})")

        # Their docs: 419 means the session was revoked server-side, so a refresh can't
        # help and only a fresh sign-in will do.
        if res.status_code == 419:
            raise SwiggyAuthExpired("Swiggy session was revoked (HTTP 419)")

        if res.status_code == 429:
            raise SwiggyRateLimited(_retry_after_seconds(res))

        print(f"Swiggy MCP error on {path}/{tool}: {res.status_code} {res.text[:200]}")
        return None

    return None


def _retry_after_seconds(res):
    try:
        return int(float(res.headers.get("Retry-After")))
    except (TypeError, ValueError):
        return None


def _decode_mcp_body(res):
    """MCP answers as plain JSON or as an SSE 'data:' frame."""
    text = res.text or ""
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return res.json()
        except Exception:
            pass
    if "data:" in text:
        try:
            return json.loads(text.split("data:", 1)[1].strip())
        except Exception:
            pass
    return None

IST_TZ = timezone(timedelta(hours=5, minutes=30))

def clean_placed_at(status_text, created_at_raw=None):
    if created_at_raw:
        try:
            if isinstance(created_at_raw, (int, float)) or (isinstance(created_at_raw, str) and created_at_raw.isdigit()):
                val = float(created_at_raw)
                if val > 1e11: val = val / 1000.0
                dt = datetime.fromtimestamp(val, tz=timezone.utc)
            else:
                dt_str = str(created_at_raw).replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            dt_ist = dt.astimezone(IST_TZ)
            return dt_ist.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            pass

    if not status_text:
        return "Recently"
    text = str(status_text)
    if "delivered on " in text.lower():
        parts = text.split("delivered on ")
        if len(parts) > 1:
            rest = parts[1]
            if " by " in rest:
                return rest.split(" by ")[0].strip()
            return rest.strip()
    return text

@api_view(['GET'])
def swiggy_status(request):
    u = get_user_profile_by_req(request)
    return Response({
        **swiggy_session_state(u),
        "phone_number": u.phone_number,
        "user_id": u.id,
        "user_name": u.name
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_send_otp(request):
    u = get_user_profile_by_req(request)
    raw_phone = request.data.get("phone_number") or request.data.get("phone") or u.phone_number
    phone_number = str(raw_phone).strip()
    if not phone_number or len(phone_number) < 10:
        return Response({"error": "Invalid phone number.", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)

    u.phone_number = phone_number
    u.save()
    return Response({"message": f"OTP sent to {phone_number} via SMS.", "success": True, "ok": True}, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_verify_otp(request):
    # Swiggy sign-in is the OAuth link, not an OTP. This used to stamp a hardcoded
    # token onto the profile, which made the app look signed in while every call failed.
    return Response({
        "error": "Swiggy sign-in happens through the Connect Swiggy link, not an OTP here.",
        "ok": False,
        "success": False,
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def swiggy_logout(request):
    u = get_user_profile_by_req(request)
    clear_swiggy_session(u)

    # Both caches, and the stale reconnect flag with them: the food cache used to
    # survive a logout and keep serving the previous session's orders.
    for cache in (get_swiggy_order_cache(u.phone_number), get_swiggy_food_order_cache(u.phone_number)):
        cache["data"] = None
        cache["auth_error"] = False
    return Response({"message": f"Logged out from Swiggy for {u.name}."}, status=status.HTTP_200_OK)

def get_swiggy_redirect_uri(request):
    """Where Swiggy sends the user back after login.

    Derived from the request so the browser comes back to whichever host it is already
    talking to — prod, UAT and a dev machine all differ, and the app answers on all of
    them. This used to be a hardcoded localhost URL, which off a dev machine is a dead
    page: the authorization code landed somewhere nothing was listening, which is why
    the URL had to be copied out of the address bar by hand.

    No query string and a trailing slash: Swiggy matches the redirect URI exactly, and
    an APPEND_SLASH redirect partway through the flow would drop the code.
    """
    base = SWIGGY_PUBLIC_CALLBACK or request.build_absolute_uri(reverse("swiggy_callback"))
    scheme, netloc, path, _query, _fragment = urlsplit(base)
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((scheme, netloc, path, "", ""))


def swiggy_frontend_root(request):
    """The app's own root, to send the browser back to once login is done.

    Behind Caddy the host carries no port and the frontend is served at the root. The
    dev-port mapping only applies when a port is explicit, so prod never reaches it —
    it used to be unconditional, which on prod produced a :5001 URL serving nothing.
    """
    if SWIGGY_APP_ROOT:
        return SWIGGY_APP_ROOT if SWIGGY_APP_ROOT.endswith("/") else SWIGGY_APP_ROOT + "/"

    host = request.get_host()
    hostname, _, port = host.partition(":")
    frontend_port = {"8000": "5173", "5002": "5001", "5003": "5001"}.get(port)
    if frontend_port:
        return f"{request.scheme}://{hostname}:{frontend_port}/"
    return f"{request.scheme}://{host}/"


# Fallback for logins started before per-user verifiers existed.
LEGACY_PKCE_VERIFIER = "SEFa4u3Kq9q9lkApAawhFbyZ-Te3pl54RMrlm5NKqa4"


def _new_pkce_pair():
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


@api_view(['GET'])
def swiggy_auth_url(request):
    u = get_user_profile_by_req(request)

    redirect_uri = get_swiggy_redirect_uri(request)
    # A fresh verifier per login attempt, stored against the user because the callback
    # may be served by a different gunicorn worker than this request.
    verifier, code_challenge = _new_pkce_pair()
    # The nonce is how the callback knows whose login this is, now that the redirect URI
    # carries no phone number. Single-use, and checked with a constant-time compare.
    nonce = secrets.token_urlsafe(16)
    state = f"{nonce}.{u.id}"

    u.swiggy_pkce_verifier = verifier
    u.swiggy_oauth_state = nonce
    # Replayed verbatim at token exchange: Swiggy matches it exactly, and this request
    # and the callback can arrive on different hostnames.
    u.swiggy_oauth_redirect_uri = redirect_uri
    u.save(update_fields=[
        "swiggy_pkce_verifier", "swiggy_oauth_state", "swiggy_oauth_redirect_uri",
    ])

    url = (
        f"{MCP_BASE}/auth/authorize?"
        f"response_type=code&"
        f"client_id={SWIGGY_CLIENT_ID}&"
        f"redirect_uri={quote(redirect_uri, safe='')}&"
        f"code_challenge={code_challenge}&"
        f"code_challenge_method=S256&"
        f"state={quote(state, safe='')}&"
        f"scope=mcp:tools"
    )
    # redirect_uri is echoed back so the deployed value can be checked with one curl.
    return Response({
        "auth_url": url,
        "redirect_uri": redirect_uri,
        "state": state,
        **swiggy_session_state(u),
    })

def _user_from_oauth_state(request):
    """Whose login this callback belongs to.

    Prefers the `state` nonce minted by swiggy_auth_url. Falls back to the old
    ?phone=/user_id lookup so a login already in flight across a deploy, and the
    paste-the-URL box, both still complete.
    """
    state = request.query_params.get("state") or request.data.get("state") or ""
    if "." in state:
        nonce, _, user_id = state.partition(".")
        try:
            u = UserProfile.objects.get(id=int(user_id))
        except (UserProfile.DoesNotExist, ValueError):
            return None
        if not nonce or not secrets.compare_digest(u.swiggy_oauth_state or "", nonce):
            return None
        return u

    phone = request.query_params.get("phone") or request.data.get("phone")
    if phone:
        return get_user_profile_by_req(request, phone_override=phone)
    return get_user_profile_by_req(request)


@api_view(['GET', 'POST'])
def swiggy_callback(request):
    is_ajax = request.query_params.get("ajax") == "1"

    def fail(reason, detail=None, http_status=status.HTTP_400_BAD_REQUEST):
        # A browser landing on a JSON error is just another dead end, so send it back
        # to the app with a reason it can show. Logged either way.
        print(f"Swiggy callback failed ({reason}): {detail}")
        if is_ajax:
            return Response({"error": reason, "details": detail, "success": False}, status=http_status)
        return redirect(f"{swiggy_frontend_root(request)}?swiggy_error={quote(reason, safe='')}")

    u = _user_from_oauth_state(request)
    if u is None:
        return fail("bad_state", "No login in flight matched this callback.")

    code = request.query_params.get("code") or request.data.get("code")
    if not code:
        return fail("no_code", "No authorization code provided.")

    # The string sent to /auth/authorize, not a fresh guess: Swiggy matches it exactly.
    redirect_uri = u.swiggy_oauth_redirect_uri or get_swiggy_redirect_uri(request)

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": u.swiggy_pkce_verifier or LEGACY_PKCE_VERIFIER,
        "redirect_uri": redirect_uri,
        "client_id": SWIGGY_CLIENT_ID,
    }

    try:
        res = requests.post(f"{MCP_BASE}/auth/token", json=payload, timeout=10.0)
        try:
            data = res.json()
        except Exception:
            data = {}

        if res.status_code != 200 or not data.get("access_token"):
            # Keep the error, drop the tokens: never log the response wholesale, since a
            # successful body would contain the access token.
            return fail("exchange_failed", f"HTTP {res.status_code} {data.get('error', '')} {data.get('error_description', '')}".strip())

        store_swiggy_tokens(u, data, save=False)
        u.swiggy_pkce_verifier = None
        u.swiggy_oauth_state = None
        u.swiggy_oauth_redirect_uri = None
        u.save()

        # A fresh session: clear any stale "reconnect" flag on both caches.
        get_swiggy_order_cache(u.phone_number)["auth_error"] = False
        get_swiggy_food_order_cache(u.phone_number)["auth_error"] = False

        if is_ajax:
            return Response({"message": "Successfully connected", "success": True}, status=status.HTTP_200_OK)

        # Orders are not synced here on purpose: it meant up to ~15 sequential calls
        # before the browser moved, so login sat on a blank tab. The landing page asks
        # for a refresh instead, where the wait is visible.
        return redirect(f"{swiggy_frontend_root(request)}?swiggy_connected=1")
    except requests.RequestException as e:
        return fail("exchange_failed", str(e), http_status=status.HTTP_502_BAD_GATEWAY)

import re


def mcp_text_payloads(resp_json):
    """Every JSON object carried in a JSON-RPC result's text content blocks."""
    out = []
    if not isinstance(resp_json, dict):
        return out
    content = (resp_json.get("result") or {}).get("content") or []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            try:
                out.append(json.loads(item.get("text", "{}")))
            except Exception:
                pass
    return out


def rescale_item_lines(weights, target_sum):
    """Scale line totals so they add up to target_sum exactly.

    Discounts mean the raw line prices can exceed what was actually paid. Scaling
    proportionally keeps each item's relative share honest, and the last line absorbs
    the rounding remainder so the total lands exactly.
    """
    target_sum = round(float(target_sum), 2)
    total_weight = sum(weights)
    if total_weight <= 0:
        if not weights:
            return []
        even = round(target_sum / len(weights), 2)
        lines = [even] * len(weights)
        lines[-1] = round(target_sum - even * (len(weights) - 1), 2)
        return lines

    lines = []
    running = 0.0
    for idx, w in enumerate(weights):
        if idx == len(weights) - 1:
            price = round(target_sum - running, 2)
        else:
            price = round(target_sum * (w / total_weight), 2)
            running = round(running + price, 2)
        lines.append(price)
    return lines


def _food_line_weight(item):
    """What one order line cost, before the bill-level reconciliation."""
    qty = int(item.get("quantity") or 1)
    base = 0.0
    for key in ("total", "final_price", "subtotal"):
        try:
            val = float(item.get(key) or 0.0)
        except (TypeError, ValueError):
            val = 0.0
        if val > 0:
            base = val
            break
    if base <= 0:
        try:
            base = float(item.get("base_price") or 0.0) * max(1, qty)
        except (TypeError, ValueError):
            base = 0.0

    extras = 0.0
    for group in ("variants", "addons"):
        for sub in (item.get(group) or []):
            if isinstance(sub, dict):
                try:
                    extras += float(sub.get("price") or 0.0)
                except (TypeError, ValueError):
                    pass
    try:
        extras += float(item.get("packing_charges") or 0.0)
    except (TypeError, ValueError):
        pass
    return max(0.0, base + extras)


def _food_item_name(item):
    name = item.get("name") or "Food Item"
    variant_names = [
        str(v.get("name")) for v in (item.get("variants") or [])
        if isinstance(v, dict) and v.get("name")
    ]
    if variant_names:
        return f"{name} ({', '.join(variant_names)})"
    return name


def parse_swiggy_food_orders(orders_payload, details_by_id=None):
    """Swiggy food orders -> the same order dict Instamart and Blinkit produce.

    Pure, so it unit-tests without touching the network. `orders_payload` is the
    unwrapped `get_food_orders` body; `details_by_id` maps order id to the unwrapped
    `get_food_order_details` body for exact item prices.
    """
    details_by_id = details_by_id or {}
    data = orders_payload.get("data") if isinstance(orders_payload, dict) else None
    raw_orders = (data or {}).get("orders") if isinstance(data, dict) else None
    if raw_orders is None and isinstance(orders_payload, dict):
        raw_orders = orders_payload.get("orders")
    parsed = []

    for raw in (raw_orders or []):
        if not isinstance(raw, dict):
            continue
        ord_id = str(raw.get("orderId") or raw.get("order_id") or "").strip()
        if not ord_id:
            continue
        # An in-flight order has no final bill yet and its total still moves.
        if raw.get("isActiveOrder"):
            continue

        detail_body = details_by_id.get(ord_id) or {}
        detail = (detail_body.get("data") or {}).get("order") if isinstance(detail_body, dict) else None
        detail = detail or {}

        try:
            total_amount = float(detail.get("order_total") or raw.get("orderTotal") or 0.0)
        except (TypeError, ValueError):
            total_amount = 0.0

        ordered_time = detail.get("order_time") or raw.get("orderedTime")
        placed_at = clean_placed_at(
            raw.get("orderStatus") or raw.get("orderDeliveryStatus"),
            created_at_raw=ordered_time,
        )

        items_raw = [it for it in (detail.get("order_items") or []) if isinstance(it, dict)]
        names, weights, quantities = [], [], []
        for it in items_raw:
            names.append(_food_item_name(it))
            weights.append(_food_line_weight(it))
            quantities.append(int(it.get("quantity") or 1))

        def _num(key):
            try:
                return float(detail.get(key) or 0.0)
            except (TypeError, ValueError):
                return 0.0

        # Fees the diner pays on top of the food itself. Deliberately not including
        # discounts here: those are spread across the items by the rescale below.
        charges = max(0.0, round(_num("order_tax") + _num("order_delivery_charge"), 2))
        if charges > total_amount:
            charges = 0.0

        if names:
            target = round(total_amount - charges, 2)
            lines = rescale_item_lines(weights, target)
            item_details = [
                {"name": n, "price": p, "quantity": q}
                for n, p, q in zip(names, lines, quantities)
            ]
        else:
            # No detail call, or an empty bill: one line so the split UI still works.
            label = raw.get("restaurantName") or "Swiggy Food order"
            item_details = [{"name": label, "price": round(total_amount, 2), "quantity": 1}]
            names = [label]

        # Derived last, so sum(prices) + other_charges == total_amount exactly and is
        # never negative. ItemizedSplitModal drops a negative value and then its own
        # arithmetic stops matching the total.
        other_charges = round(total_amount - sum(i["price"] for i in item_details), 2)
        if other_charges < 0:
            other_charges = 0.0

        parsed.append({
            "order_id": ord_id,
            "order_type": FOOD_PLATFORM,
            "placed_at": placed_at,
            "total_amount": round(total_amount, 2),
            "product_names": names,
            "item_details": item_details,
            "other_charges": other_charges,
            # order_store already looks for orderTime when normalising to IST and when
            # sorting, so food and Instamart interleave correctly with no changes there.
            "orderTime": ordered_time,
            "restaurant_name": detail.get("restaurant_name") or raw.get("restaurantName") or "",
        })

    return parsed


def parse_swiggy_orders_json(resp_json, headers=None):
    raw_orders = []
    if "result" in resp_json and "content" in resp_json["result"]:
        for item in resp_json["result"]["content"]:
            if item.get("type") == "text":
                try:
                    parsed = json.loads(item.get("text", "{}"))
                    if "orders" in parsed:
                        raw_orders = parsed["orders"]
                    elif isinstance(parsed, list):
                        raw_orders = parsed
                except Exception:
                    pass
    elif isinstance(resp_json, list):
        raw_orders = resp_json
    elif isinstance(resp_json, dict) and "orders" in resp_json:
        raw_orders = resp_json["orders"]
    
    parsed_orders = []
    for ord_item in raw_orders:
        ord_id = str(ord_item.get("orderId") or ord_item.get("order_id") or ord_item.get("id") or "").strip()
        if not ord_id or ord_id == "None":
            continue

        bill = ord_item.get("billDetails") or {}
        tot_amt = float(ord_item.get("totalAmount") or ord_item.get("order_total") or ord_item.get("total_amount") or bill.get("grandTotal") or 0.0)
        
        created_raw = ord_item.get("createdAt") or ord_item.get("orderTime") or ord_item.get("created_at") or ord_item.get("order_time")
        status_raw = ord_item.get("currentStatus") or ord_item.get("order_status_text") or ord_item.get("status") or ord_item.get("placed_at")
        placed_clean = clean_placed_at(status_raw, created_at_raw=created_raw)

        items_raw = ord_item.get("order_items") or ord_item.get("items") or []
        item_total = float(bill.get("itemTotal") or bill.get("item_total") or tot_amt)
        
        prod_names = []
        item_details = []
        
        # Try fetching real per-item prices from track_order if headers are available
        track_items = []
        if headers:
            try:
                addr = ord_item.get("deliveryAddress") or {}
                lat = float(addr.get("lat") or 28.4595)
                lng = float(addr.get("lng") or 77.0266)
                
                track_payload = {
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "track_order", "arguments": {"orderId": ord_id, "lat": lat, "lng": lng}}
                }
                tr_res = requests.post(f"{MCP_BASE}/im", json=track_payload, headers=headers, timeout=5.0)
                if tr_res.status_code == 200:
                    sc = tr_res.json().get("result", {}).get("structuredContent", {})
                    track_items = sc.get("items", [])
            except Exception as e:
                print(f"track_order price fetch skipped for {ord_id}: {e}")

        # Real other charges (handling/delivery) = grandTotal - itemTotal
        other_chg = max(0.0, round(tot_amt - item_total, 2))

        if track_items:
            sum_t = 0.0
            tracked_names = []
            for ti in track_items:
                raw_n = ti.get("name") or "Instamart Item"
                m_qty = re.match(r'^(\d+)\s*x\s*(.*)$', raw_n.strip(), re.IGNORECASE)
                if m_qty:
                    q = int(m_qty.group(1))
                    clean_n = m_qty.group(2).strip()
                else:
                    q = int(ti.get("quantity") or 1)
                    clean_n = raw_n.strip()

                raw_p = str(ti.get("price") or "0")
                p_val = float(re.sub(r'[^\d.]', '', raw_p) or 0.0)
                
                prod_names.append(clean_n)
                # Store total line price for all units directly on price
                item_details.append({"name": clean_n, "price": p_val, "quantity": q})
                sum_t += p_val
                tracked_names.append(clean_n.lower())

            # Detect any items in items_raw that were omitted from track_order (e.g. Vim Dishwash in 0704)
            missing_items = []
            for gi in items_raw:
                g_name = (gi.get("name") if isinstance(gi, dict) else str(gi)) or "Instamart Item"
                g_qty = int(gi.get("quantity") if isinstance(gi, dict) else 1) or 1
                if not any(g_name.lower() in tn or tn in g_name.lower() for tn in tracked_names):
                    missing_items.append((g_name, g_qty))

            if missing_items:
                rem_amt = max(0.0, round(item_total - sum_t, 2))
                tot_missing_count = len(missing_items)
                for m_name, m_q in missing_items:
                    m_line_price = round(rem_amt / tot_missing_count, 2)
                    prod_names.append(m_name)
                    item_details.append({"name": m_name, "price": m_line_price, "quantity": m_q})
        else:
            has_explicit = any(float(it.get("price") or it.get("unit_price") or it.get("unitPrice") or it.get("item_price") or 0.0) > 0 for it in items_raw if isinstance(it, dict))

            if has_explicit:
                for it in items_raw:
                    if isinstance(it, dict):
                        p_name = it.get("name") or "Instamart Item"
                        p_qty = int(it.get("quantity") or 1)
                        p_price = float(it.get("price") or it.get("unit_price") or it.get("unitPrice") or it.get("item_price") or 0.0)
                        prod_names.append(p_name)
                        item_details.append({"name": p_name, "price": p_price, "quantity": p_qty})
            else:
                dict_items = [it for it in items_raw if isinstance(it, dict)]
                if not dict_items:
                    dict_items = [{"name": str(it), "quantity": 1} for it in items_raw]

                total_qty = sum(int(it.get("quantity") or 1) for it in dict_items)
                if total_qty == 0: total_qty = max(1, len(dict_items))
                
                avg_price = round(item_total / total_qty, 2)
                sum_prod = 0.0

                for idx, it in enumerate(dict_items):
                    p_name = it.get("name") or "Instamart Item"
                    p_qty = int(it.get("quantity") or 1)
                    
                    if idx == len(dict_items) - 1:
                        rem = round(item_total - sum_prod, 2)
                        p_price = round(rem / p_qty, 2) if p_qty > 0 else 0.0
                    else:
                        p_price = avg_price
                        
                    prod_names.append(p_name)
                    item_details.append({"name": p_name, "price": p_price, "quantity": p_qty})
                    sum_prod += (p_price * p_qty)

        parsed_orders.append({
            "order_id": ord_id,
            "order_type": INSTAMART_PLATFORM,
            "placed_at": placed_clean,
            "total_amount": tot_amt,
            "product_names": prod_names,
            "item_details": item_details,
            "other_charges": other_chg
        })
    return parsed_orders

def fetch_swiggy_food_orders_internal(user_profile, force_refresh=False):
    """Swiggy food orders, stored under their own platform so ids can't collide."""
    cache = get_swiggy_food_order_cache(user_profile.phone_number)
    token = user_profile.swiggy_access_token
    if not token or token == "MANUAL_JSON_OVERRIDE":
        return OrderStoreManager.get_saved_orders(user_profile, FOOD_PLATFORM)

    now = time.time()
    if not force_refresh and cache.get("data") and (now - cache.get("timestamp", 0) < CACHE_TTL_SECONDS):
        return cache["data"]

    fresh_orders = []
    # get_food_orders requires an addressId purely to resolve coordinates; it does not
    # filter, so any address returns the full history.
    address_id = cache.get("address_id")
    if not address_id:
        addr_body = swiggy_mcp_call(user_profile, FOOD_PATH, "get_addresses")
        for payload in mcp_text_payloads(addr_body or {}):
            addresses = (payload.get("data") or {}).get("addresses") or payload.get("addresses") or []
            for addr in addresses:
                if isinstance(addr, dict) and (addr.get("addressId") or addr.get("id")):
                    address_id = str(addr.get("addressId") or addr.get("id"))
                    break
            if address_id:
                break
        cache["address_id"] = address_id

    if address_id:
        orders_body = swiggy_mcp_call(
            user_profile, FOOD_PATH, "get_food_orders",
            {"addressId": address_id, "activeOnly": False, "orderCount": FOOD_ORDER_COUNT},
        )
        payloads = mcp_text_payloads(orders_body or {})
        orders_payload = payloads[0] if payloads else {}

        # Only orders we haven't already stored need the per-order details call.
        listed_ids = [
            str(o.get("orderId") or o.get("order_id") or "").strip()
            for o in ((orders_payload.get("data") or {}).get("orders") or [])
            if isinstance(o, dict)
        ]
        already = {
            str(r.get("order_id"))
            for r in OrderStoreManager.get_saved_orders(user_profile, FOOD_PLATFORM)
            if r.get("item_details")
        }

        details_by_id = {}
        for oid in listed_ids:
            if not oid or oid in already:
                continue
            detail = swiggy_mcp_call(user_profile, FOOD_PATH, "get_food_order_details", {"orderId": oid})
            payloads = mcp_text_payloads(detail or {})
            if payloads:
                details_by_id[oid] = payloads[0]
            time.sleep(0.3)

        parsed = parse_swiggy_food_orders(orders_payload, details_by_id)
        # Item rows are written only on first insert and are then preferred forever,
        # so never save an order whose details call failed with guessed prices.
        fresh_orders = [
            o for o in parsed
            if str(o["order_id"]) in already or str(o["order_id"]) in details_by_id
        ]

    merged = OrderStoreManager.save_and_merge_orders(user_profile, FOOD_PLATFORM, fresh_orders)
    cache["data"] = merged
    cache["timestamp"] = now
    return merged


def fetch_swiggy_orders_internal(user_profile, force_refresh=False):
    """Every Swiggy order — Instamart and food — as one date-sorted list.

    Returns stored orders rather than an empty list when Swiggy is unreachable, but
    records an auth error so the UI can ask for a reconnect instead of quietly
    presenting months-old data as current.
    """
    cache = get_swiggy_order_cache(user_profile.phone_number)
    token = user_profile.swiggy_access_token

    def _stored():
        return _sort_orders_descending(
            OrderStoreManager.get_saved_orders(user_profile, INSTAMART_PLATFORM)
            + OrderStoreManager.get_saved_orders(user_profile, FOOD_PLATFORM)
        )

    if not token or token == "MANUAL_JSON_OVERRIDE":
        stored = _stored()
        cache["data"] = stored
        return stored

    now = time.time()
    if not force_refresh and cache.get("data") and (now - cache.get("timestamp", 0) < CACHE_TTL_SECONDS):
        return cache["data"]

    instamart_rows, auth_expired, rate_limited = None, False, False
    try:
        body = swiggy_mcp_call(user_profile, IM_PATH, "get_orders", timeout=10.0)
        if body is not None:
            headers = {
                "Authorization": f"Bearer {user_profile.swiggy_access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            fresh = parse_swiggy_orders_json(body, headers=headers)
            instamart_rows = OrderStoreManager.save_and_merge_orders(
                user_profile, INSTAMART_PLATFORM, fresh)
    except SwiggyAuthExpired as e:
        auth_expired = True
        print(f"Swiggy session expired for {user_profile.name}: {e}")
    except SwiggyRateLimited as e:
        # Not an auth problem: serve what's stored and let the next refresh try again.
        rate_limited = True
        print(f"Swiggy rate limited for {user_profile.name}: {e}")
    except Exception as e:
        print("Error fetching Swiggy Instamart orders:", e)

    food_rows = None
    if not auth_expired and not rate_limited:
        try:
            food_rows = fetch_swiggy_food_orders_internal(user_profile, force_refresh=force_refresh)
        except SwiggyAuthExpired as e:
            auth_expired = True
            print(f"Swiggy session expired for {user_profile.name}: {e}")
        except SwiggyRateLimited as e:
            rate_limited = True
            print(f"Swiggy rate limited for {user_profile.name}: {e}")
        except Exception as e:
            print("Error fetching Swiggy food orders:", e)

    cache["auth_error"] = auth_expired
    if instamart_rows is None:
        instamart_rows = OrderStoreManager.get_saved_orders(user_profile, INSTAMART_PLATFORM)
    if food_rows is None:
        food_rows = OrderStoreManager.get_saved_orders(user_profile, FOOD_PLATFORM)

    merged_orders = _sort_orders_descending(list(instamart_rows) + list(food_rows))
    cache["data"] = merged_orders
    cache["timestamp"] = now
    return merged_orders

@api_view(['POST'])
def swiggy_sync_manual(request):
    u = get_user_profile_by_req(request)
    try:
        json_data = request.data.get("json_data", {})
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        
        parsed = parse_swiggy_orders_json(json_data)
        
        # update profile to indicate manual login
        u.swiggy_access_token = "MANUAL_JSON_OVERRIDE"
        u.save()
        
        merged = OrderStoreManager.save_and_merge_orders(u, INSTAMART_PLATFORM, parsed)
        cache = get_swiggy_order_cache(u.phone_number)
        cache["data"] = merged
        cache["timestamp"] = time.time()
        
        return Response({"message": "Orders synced manually", "count": len(merged)}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": f"Failed to parse JSON: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def swiggy_orders(request):
    u = get_user_profile_by_req(request)
    orders_list = fetch_swiggy_orders_internal(u, force_refresh=request.query_params.get("refresh") == "true")
    output_orders = []
    for ord_item in orders_list:
        ord_id = str(ord_item.get("order_id", ""))
        existing_exp = Expense.objects.filter(
            order_expense_query(ord_id, swiggy_platform_label(ord_item.get("order_type")))
        ).first()
        
        ord_copy = dict(ord_item)
        if existing_exp:
            ord_copy["is_split"] = True
            parsed_notes = None
            if existing_exp.notes:
                try:
                    parsed_notes = json.loads(existing_exp.notes)
                except Exception:
                    pass
            
            split_mode_val = "ITEMIZED"
            items_saved = []
            if isinstance(parsed_notes, dict):
                split_mode_val = parsed_notes.get("split_mode", "ITEMIZED")
                items_saved = parsed_notes.get("items", [])
            elif isinstance(parsed_notes, list):
                items_saved = parsed_notes

            ord_copy["existing_split"] = {
                "expense_id": existing_exp.id,
                "split_mode": split_mode_val,
                "notes_items": items_saved
            }
        else:
            ord_copy["is_split"] = False
            ord_copy["existing_split"] = None

        output_orders.append(ord_copy)

    return Response({
        "orders": output_orders,
        "cached": not request.query_params.get("refresh") == "true",
        "needs_reconnect": swiggy_session_state(u)["needs_reconnect"],
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_order_cart_details(request):
    u = get_user_profile_by_req(request)
    order_id = request.data.get("order_id")
    cache = get_swiggy_order_cache(u.phone_number)
    orders_list = cache.get("data") or []
    target_ord = next((o for o in orders_list if str(o.get("order_id")) == str(order_id)), None)

    if not target_ord:
        return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "order_id": order_id,
        "item_details": target_ord.get("item_details", []),
        "other_charges": target_ord.get("other_charges", 0.0)
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_split_order(request):
    try:
        res = GrocerySplitEngine.process_split(
            platform_name=swiggy_platform_label(request.data.get("platform")),
            group_id=request.data.get("group_id"),
            buyer_id=request.data.get("buyer_id"),
            order_id=request.data.get("order_id", "Swiggy Order"),
            total_amount=float(request.data.get("total_amount", 0.0)),
            split_mode=request.data.get("split_mode", "BILL_LEVEL"),
            item_splits_data=request.data.get("item_splits", []),
            bill_split_data=request.data.get("bill_split", {}),
            description=request.data.get("description"),
            placed_at=request.data.get("placed_at"),
            actor_id=request.data.get("actor_id")
        )
        return Response(res, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def swiggy_remove_split(request):
    order_id = request.data.get("order_id")
    if not order_id:
        return Response({"error": "order_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    res = GrocerySplitEngine.remove_split(
        order_id,
        actor_id=request.data.get("actor_id"),
        platform_name=swiggy_platform_label(request.data.get("platform")),
    )
    return Response(res, status=status.HTTP_200_OK)
