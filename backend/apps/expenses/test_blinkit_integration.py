from rest_framework.test import APITestCase
from rest_framework import status
from apps.users.models import UserProfile
from apps.groups.models import Group

class BlinkitIntegrationTests(APITestCase):
    def setUp(self):
        self.user1 = UserProfile.objects.create(username="venkatesh", name="Venkatesh", email="venk@test.com", password="10", phone_number="6382247549")
        self.user2 = UserProfile.objects.create(username="alex", name="Alex", email="alex@test.com", password="10")
        self.group = Group.objects.create(name="Groceries 🛒", category="HOME", currency="₹")
        self.group.members.add(self.user1, self.user2)

    def test_login_endpoint(self):
        res = self.client.post('/api/users/login/', {'username': 'venkatesh', 'password': '10'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['user']['name'], 'Venkatesh')

    def test_blinkit_status_endpoint(self):
        res = self.client.get('/api/blinkit/status/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('is_logged_in', res.data)

    def test_quick_bill_split_order(self):
        payload = {
            "group_id": self.group.id,
            "buyer_id": self.user1.id,
            "order_id": "2577189469",
            "description": "Blinkit Order #2577189469",
            "total_amount": 646.0,
            "split_mode": "BILL_LEVEL",
            "bill_split": {
                "type": "EQUAL",
                "member_ids": [self.user1.id, self.user2.id]
            }
        }
        res = self.client.post('/api/blinkit/split_order/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['owed_breakdown'][self.user1.id], 323.0)
        self.assertEqual(res.data['owed_breakdown'][self.user2.id], 323.0)

    def test_itemized_split_order(self):
        payload = {
            "group_id": self.group.id,
            "buyer_id": self.user1.id,
            "order_id": "2432253687",
            "description": "Blinkit Personal & Shared",
            "total_amount": 316.0,
            "split_mode": "ITEMIZED",
            "item_splits": [
                {
                    "name": "Fiama Shower Gel",
                    "price": 200.0,
                    "split_type": "ALL"
                },
                {
                    "name": "Joy Moisturizing Cream",
                    "price": 116.0,
                    "split_type": "PERSONAL"
                }
            ]
        }
        res = self.client.post('/api/blinkit/split_order/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Venkatesh pays 316. Item 1 (200) split 100 each. Item 2 (116) personal to Venkatesh -> 116.
        # Venkatesh owes 100 + 116 = 216. Alex owes 100.
        self.assertEqual(res.data['owed_breakdown'][self.user1.id], 216.0)
        self.assertEqual(res.data['owed_breakdown'][self.user2.id], 100.0)

    def test_parse_blinkit_order_details_comma_price(self):
        from apps.expenses.blinkit_views import parse_blinkit_order_details_v2
        mock_data = {
            "is_success": True,
            "response": {
                "snippets": [
                    {
                        "widget_type": "z_v3_image_text_snippet",
                        "data": {
                            "title": {"text": "Gulab Groundnut Oil"},
                            "subtitle1": {"text": "1 l x 1"},
                            "subtitle3": {"text": "₹1,499 ₹1,289"}
                        }
                    },
                    {
                        "widget_type": "cart_bill_item",
                        "data": {
                            "left_header": {"text": "Bill Total"},
                            "right_header": {"text": "₹1,298"}
                        }
                    }
                ]
            }
        }
        res = parse_blinkit_order_details_v2(mock_data)
        self.assertIsNotNone(res)
        self.assertEqual(res["item_details"][0]["price"], 1289.0)
        self.assertEqual(res["total_amount"], 1298.0)
        self.assertEqual(res["other_charges"], 9.0)


    def test_order_history_total_ignores_return_card_date(self):
        from apps.expenses.blinkit_views import extract_blinkit_orders_from_sdui

        def card(order_id, title, underlined):
            return {
                "widget_type": "order_history_container_vr",
                "tracking": {"common_attributes": {
                    "order_id": order_id,
                    "deeplink": f"grofers://widgetized/order_details_v2?cart_id=900&order_id={order_id}"
                }},
                "data": {"items": [{"data": {"title": {"text": title}, "left_underlined_subtitle": {"text": underlined}}}]}
            }

        orders = extract_blinkit_orders_from_sdui([
            card("101", "Exchange completed", "19 Sep, 12:41 am"),
            card("102", "Delivered", "₹1,401"),
        ])
        totals = {o["order_id"]: o["total_amount"] for o in orders}
        self.assertEqual(totals["101"], 0.0)
        self.assertEqual(totals["102"], 1401.0)
