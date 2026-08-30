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
