from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse

from rest_framework.test import APITestCase

from apps.users.models import UserProfile


class TokenResponse:
    status_code = 200

    def json(self):
        return {"access_token": "new-access", "refresh_token": "new-refresh"}


def redirect_uri_of(auth_url):
    return unquote(parse_qs(urlparse(auth_url).query)["redirect_uri"][0])


class SwiggyLoginTests(APITestCase):
    def setUp(self):
        self.venkatesh = UserProfile.objects.create(username="venkatesh", name="Venkatesh", email="v@test.com", phone_number="6382247549")
        self.no_phone = UserProfile.objects.create(username="rahul", name="Rahul", email="r@test.com", phone_number="")

    def test_login_link_never_borrows_another_persons_phone(self):
        res = self.client.get(f'/api/swiggy/auth_url/?user_id={self.no_phone.id}')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("6382247549", redirect_uri_of(res.data["auth_url"]))

    def test_pasted_callback_finishes_login_for_the_person_pasting_it(self):
        self.client.get(f'/api/swiggy/auth_url/?user_id={self.no_phone.id}')
        with patch("apps.expenses.swiggy_views.requests.post", return_value=TokenResponse()), \
             patch("apps.expenses.swiggy_views.fetch_swiggy_orders_internal", return_value=[]):
            # What the frontend sends after the localhost address is pasted back
            res = self.client.get(f'/api/swiggy/callback/?code=abc&phone=&user_id={self.no_phone.id}&ajax=1')
        self.assertEqual(res.status_code, 200, res.data)
        self.no_phone.refresh_from_db()
        self.venkatesh.refresh_from_db()
        self.assertEqual(self.no_phone.swiggy_access_token, "new-access")
        self.assertFalse(self.venkatesh.swiggy_access_token)

    def test_each_login_link_gets_its_own_verifier(self):
        self.client.get(f'/api/swiggy/auth_url/?user_id={self.venkatesh.id}')
        self.venkatesh.refresh_from_db()
        first = self.venkatesh.swiggy_pkce_verifier
        self.client.get(f'/api/swiggy/auth_url/?user_id={self.venkatesh.id}')
        self.venkatesh.refresh_from_db()
        # Why the page must not fetch a link on every load: the old one stops working
        self.assertNotEqual(first, self.venkatesh.swiggy_pkce_verifier)
