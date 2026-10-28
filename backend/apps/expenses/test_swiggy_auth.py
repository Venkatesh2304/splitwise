"""The Swiggy OAuth round trip.

Covers the things that used to be broken silently: a redirect URI pointing at a dead
localhost page, a reconnect that could not identify the user, an expired session still
reporting itself as signed in, and a refresh that only ever ran too late to work.
"""
import base64
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from io import StringIO

from apps.users.models import UserProfile
from apps.expenses import swiggy_views
from apps.expenses.grocery_engine.state import get_swiggy_order_cache

PROD = {"HTTP_HOST": "ramasplit.duckdns.org", "HTTP_X_FORWARDED_PROTO": "https"}
PROD_CALLBACK = "https://ramasplit.duckdns.org/api/swiggy/callback/"


def jwt_expiring(delta):
    """A token shaped like Swiggy's: three dots, exp in the payload."""
    exp = int((datetime.now(timezone.utc) + delta).timestamp())
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class SwiggyAuthUrlTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(
            username="akash", name="Akash", email="a@example.com", phone_number="6382247549"
        )

    def test_defaults_to_localhost_because_swiggy_whitelists_by_domain(self):
        # Swiggy refuses a redirect it has not whitelisted ("this client isn't supported
        # for Swiggy MCP sign-in yet"), and only localhost works without that, so the
        # default must not be our own domain or sign-in breaks outright.
        res = self.client.get(reverse("swiggy_auth_url"), {"user_id": self.user.id}, **PROD)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["redirect_uri"], "http://localhost:8000/api/swiggy/callback/")
        self.assertFalse(res.json()["public_callback"])
        # Identity rides in `state` now, so no query string to break exact matching.
        self.assertNotIn("phone=", res.json()["redirect_uri"])

    def test_whitelisted_callback_is_used_when_configured(self):
        with patch.object(swiggy_views, "SWIGGY_PUBLIC_CALLBACK", PROD_CALLBACK):
            res = self.client.get(reverse("swiggy_auth_url"), {"user_id": self.user.id}, **PROD)
        self.assertEqual(res.json()["redirect_uri"], PROD_CALLBACK)
        self.assertTrue(res.json()["public_callback"])
        self.assertIn("https%3A%2F%2Framasplit.duckdns.org%2Fapi%2Fswiggy%2Fcallback%2F",
                      res.json()["auth_url"])

    def test_each_login_gets_a_fresh_verifier_and_state(self):
        first = self.client.get(reverse("swiggy_auth_url"), {"user_id": self.user.id}, **PROD).json()
        self.user.refresh_from_db()
        first_verifier = self.user.swiggy_pkce_verifier

        second = self.client.get(reverse("swiggy_auth_url"), {"user_id": self.user.id}, **PROD).json()
        self.user.refresh_from_db()

        self.assertNotEqual(first["state"], second["state"])
        self.assertNotEqual(first_verifier, self.user.swiggy_pkce_verifier)
        # Stale state must not be accepted once a newer login has started.
        self.assertTrue(self.user.swiggy_oauth_state)
        self.assertNotEqual(first["state"].split(".")[0], self.user.swiggy_oauth_state)

    def test_redirect_uri_is_remembered_for_the_exchange(self):
        with patch.object(swiggy_views, "SWIGGY_PUBLIC_CALLBACK", PROD_CALLBACK):
            self.client.get(reverse("swiggy_auth_url"), {"user_id": self.user.id}, **PROD)
        self.user.refresh_from_db()
        # Stored, so the exchange replays the same string even if the config changes
        # or the callback arrives on a different host.
        self.assertEqual(self.user.swiggy_oauth_redirect_uri, PROD_CALLBACK)


class SwiggyCallbackTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(
            username="akash", name="Akash", email="a@example.com", phone_number="6382247549"
        )
        with patch.object(swiggy_views, "SWIGGY_PUBLIC_CALLBACK", PROD_CALLBACK):
            self.state = self.client.get(
                reverse("swiggy_auth_url"), {"user_id": self.user.id}, **PROD
            ).json()["state"]
        self.user.refresh_from_db()

    def test_successful_callback_stores_session_and_returns_to_the_app(self):
        token = jwt_expiring(timedelta(days=5))
        captured = {}

        def fake_post(url, json=None, timeout=None, **kwargs):
            captured.update(json or {})
            return FakeResponse({
                "access_token": token, "refresh_token": "refresh-1", "expires_in": 432000,
            })

        with patch.object(swiggy_views.requests, "post", side_effect=fake_post):
            res = self.client.get(
                reverse("swiggy_callback"), {"code": "abc", "state": self.state}, **PROD
            )

        # Replayed verbatim, not rebuilt: Swiggy matches it exactly.
        self.assertEqual(captured["redirect_uri"], PROD_CALLBACK)
        self.assertEqual(captured["code_verifier"], self.user.swiggy_pkce_verifier)

        self.user.refresh_from_db()
        self.assertEqual(self.user.swiggy_access_token, token)
        self.assertEqual(self.user.swiggy_refresh_token, "refresh-1")
        self.assertIsNotNone(self.user.swiggy_token_expires_at)
        # The login in flight is finished with.
        self.assertIsNone(self.user.swiggy_oauth_state)
        self.assertIsNone(self.user.swiggy_pkce_verifier)

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res["Location"], "https://ramasplit.duckdns.org/?swiggy_connected=1")

    def test_state_is_single_use(self):
        with patch.object(swiggy_views.requests, "post", return_value=FakeResponse(
            {"access_token": jwt_expiring(timedelta(days=5)), "expires_in": 432000}
        )):
            self.client.get(reverse("swiggy_callback"), {"code": "abc", "state": self.state}, **PROD)
            replay = self.client.get(
                reverse("swiggy_callback"), {"code": "abc", "state": self.state}, **PROD
            )
        self.assertEqual(replay.status_code, 302)
        self.assertIn("swiggy_error=bad_state", replay["Location"])

    def test_another_users_state_cannot_drive_this_callback(self):
        other = UserProfile.objects.create(
            username="other", name="Other", email="o@example.com", phone_number="9000000000"
        )
        forged = f"not-the-nonce.{other.id}"
        res = self.client.get(reverse("swiggy_callback"), {"code": "abc", "state": forged}, **PROD)
        self.assertIn("swiggy_error=bad_state", res["Location"])
        other.refresh_from_db()
        self.assertIsNone(other.swiggy_access_token)

    def test_failed_exchange_returns_to_the_app_not_a_json_dead_end(self):
        with patch.object(swiggy_views.requests, "post", return_value=FakeResponse(
            {"error": "invalid_grant", "error_description": "bad redirect_uri"}, status_code=400
        )):
            res = self.client.get(
                reverse("swiggy_callback"), {"code": "abc", "state": self.state}, **PROD
            )
        self.assertEqual(res.status_code, 302)
        self.assertIn("swiggy_error=exchange_failed", res["Location"])
        self.user.refresh_from_db()
        self.assertIsNone(self.user.swiggy_access_token)

    def test_ajax_callback_still_answers_json_for_the_paste_box(self):
        with patch.object(swiggy_views.requests, "post", return_value=FakeResponse(
            {"access_token": jwt_expiring(timedelta(days=5)), "expires_in": 432000}
        )):
            res = self.client.get(
                reverse("swiggy_callback"),
                {"code": "abc", "state": self.state, "ajax": "1"}, **PROD
            )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])


class SwiggySessionStateTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(
            username="akash", name="Akash", email="a@example.com", phone_number="6382247549"
        )
        get_swiggy_order_cache(self.user.phone_number)["auth_error"] = False

    def status(self):
        return self.client.get(reverse("swiggy_status"), {"user_id": self.user.id}).json()

    def test_live_session_is_logged_in(self):
        self.user.swiggy_access_token = jwt_expiring(timedelta(days=4))
        self.user.swiggy_token_expires_at = datetime.now(timezone.utc) + timedelta(days=4)
        self.user.save()
        body = self.status()
        self.assertTrue(body["is_logged_in"])
        self.assertFalse(body["needs_reconnect"])

    def test_expired_session_is_not_logged_in_and_asks_to_reconnect(self):
        # The old behaviour: a dead token still reported is_logged_in, which hid the
        # only way back.
        self.user.swiggy_access_token = jwt_expiring(timedelta(days=-1))
        self.user.swiggy_token_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        self.user.save()
        body = self.status()
        self.assertFalse(body["is_logged_in"])
        self.assertTrue(body["needs_reconnect"])

    def test_expiry_is_read_from_the_token_when_not_stored(self):
        # Rows written before the expiry column existed.
        self.user.swiggy_access_token = jwt_expiring(timedelta(days=-1))
        self.user.save()
        self.assertFalse(self.status()["is_logged_in"])

    def test_unknown_expiry_is_not_treated_as_expired(self):
        self.user.swiggy_access_token = "MANUAL_JSON_OVERRIDE"
        self.user.save()
        body = self.status()
        self.assertTrue(body["is_logged_in"])
        self.assertTrue(body["manual_override"])

    def test_no_session_is_not_a_reconnect_prompt(self):
        body = self.status()
        self.assertFalse(body["is_logged_in"])
        self.assertFalse(body["needs_reconnect"])

    def test_logout_clears_the_session_and_the_login_in_flight(self):
        self.user.swiggy_access_token = jwt_expiring(timedelta(days=4))
        self.user.swiggy_refresh_token = "r"
        self.user.swiggy_oauth_state = "nonce"
        self.user.save()
        self.client.post(
            reverse("swiggy_logout"), {"user_id": self.user.id}, content_type="application/json"
        )
        self.user.refresh_from_db()
        self.assertIsNone(self.user.swiggy_access_token)
        self.assertIsNone(self.user.swiggy_refresh_token)
        self.assertIsNone(self.user.swiggy_oauth_state)


class SwiggyRefreshCommandTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(
            username="akash", name="Akash", email="a@example.com", phone_number="6382247549",
            swiggy_refresh_token="refresh-1",
        )

    def run_command(self, **kwargs):
        out = StringIO()
        call_command("refresh_swiggy_tokens", stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def test_token_near_expiry_is_refreshed_before_it_dies(self):
        self.user.swiggy_access_token = jwt_expiring(timedelta(hours=10))
        self.user.swiggy_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=10)
        self.user.save()

        new_token = jwt_expiring(timedelta(days=5))
        with patch.object(swiggy_views.requests, "post", return_value=FakeResponse(
            {"access_token": new_token, "refresh_token": "refresh-2", "expires_in": 432000}
        )):
            output = self.run_command()

        self.user.refresh_from_db()
        self.assertEqual(self.user.swiggy_access_token, new_token)
        # Rotation: the new refresh token replaces the old one.
        self.assertEqual(self.user.swiggy_refresh_token, "refresh-2")
        self.assertGreater(self.user.swiggy_token_expires_at, datetime.now(timezone.utc) + timedelta(days=4))
        self.assertIn("refreshed", output)

    def test_healthy_token_is_left_alone(self):
        self.user.swiggy_access_token = jwt_expiring(timedelta(days=4))
        self.user.swiggy_token_expires_at = datetime.now(timezone.utc) + timedelta(days=4)
        self.user.save()

        with patch.object(swiggy_views.requests, "post") as post:
            output = self.run_command()

        post.assert_not_called()
        self.assertIn("no action", output)

    def test_dead_refresh_token_clears_the_session_instead_of_retrying(self):
        self.user.swiggy_access_token = jwt_expiring(timedelta(hours=1))
        self.user.swiggy_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        self.user.save()

        with patch.object(swiggy_views.requests, "post", return_value=FakeResponse(
            {"error": "invalid_grant"}, status_code=400
        )):
            output = self.run_command()

        self.user.refresh_from_db()
        self.assertIsNone(self.user.swiggy_access_token)
        self.assertIsNone(self.user.swiggy_refresh_token)
        self.assertIn("needs to reconnect", output)

    def test_manual_override_is_skipped(self):
        self.user.swiggy_access_token = "MANUAL_JSON_OVERRIDE"
        self.user.save()
        with patch.object(swiggy_views.requests, "post") as post:
            self.run_command()
        post.assert_not_called()


class SwiggyMcpCallTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(
            username="akash", name="Akash", email="a@example.com", phone_number="6382247549",
            swiggy_refresh_token="refresh-1",
        )

    def test_call_refreshes_ahead_of_expiry_rather_than_after_a_401(self):
        self.user.swiggy_access_token = jwt_expiring(timedelta(seconds=30))
        self.user.swiggy_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        self.user.save()

        fresh = jwt_expiring(timedelta(days=5))
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None, **kwargs):
            calls.append(url)
            if url.endswith("/auth/token"):
                return FakeResponse({"access_token": fresh, "expires_in": 432000})
            return FakeResponse({"result": {"content": []}})

        with patch.object(swiggy_views.requests, "post", side_effect=fake_post):
            swiggy_views.swiggy_mcp_call(self.user, "/im", "get_orders")

        # The refresh happened first, unprompted by any rejection.
        self.assertTrue(calls[0].endswith("/auth/token"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.swiggy_access_token, fresh)

    def test_rate_limit_is_raised_with_retry_after(self):
        self.user.swiggy_access_token = jwt_expiring(timedelta(days=4))
        self.user.swiggy_token_expires_at = datetime.now(timezone.utc) + timedelta(days=4)
        self.user.save()

        with patch.object(swiggy_views.requests, "post", return_value=FakeResponse(
            {}, status_code=429, headers={"Retry-After": "12"}
        )):
            with self.assertRaises(swiggy_views.SwiggyRateLimited) as caught:
                swiggy_views.swiggy_mcp_call(self.user, "/im", "get_orders")
        self.assertEqual(caught.exception.retry_after, 12)

    def test_revoked_session_needs_a_fresh_sign_in(self):
        self.user.swiggy_access_token = jwt_expiring(timedelta(days=4))
        self.user.swiggy_token_expires_at = datetime.now(timezone.utc) + timedelta(days=4)
        self.user.save()

        with patch.object(swiggy_views.requests, "post", return_value=FakeResponse({}, status_code=419)):
            with self.assertRaises(swiggy_views.SwiggyAuthExpired):
                swiggy_views.swiggy_mcp_call(self.user, "/im", "get_orders")
