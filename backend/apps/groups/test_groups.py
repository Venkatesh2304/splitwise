from rest_framework.test import APITestCase
from rest_framework import status
from apps.users.models import UserProfile
from apps.groups.models import Group

class SplitwiseAPITests(APITestCase):
    def setUp(self):
        self.user1 = UserProfile.objects.create(name="Alice", email="alice@test.com")
        self.user2 = UserProfile.objects.create(name="Bob", email="bob@test.com")
        self.user3 = UserProfile.objects.create(name="Charlie", email="charlie@test.com")

    def test_create_group(self):
        url = '/api/groups/'
        data = {
            "name": "Trip to Paris",
            "description": "Euro trip",
            "category": "TRIP",
            "currency": "€",
            "member_ids": [self.user1.id, self.user2.id]
        }
        res = self.client.post(url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Group.objects.count(), 1)
        self.assertEqual(Group.objects.first().members.count(), 2)

    def test_add_expense_and_retrieve_balances(self):
        group = Group.objects.create(name="Apartment 101", category="HOME")
        group.members.add(self.user1, self.user2, self.user3)

        expense_data = {
            "group_id": group.id,
            "description": "Grocery Shopping",
            "amount": 150.0,
            "category": "FOOD",
            "split_type": "EQUAL",
            "created_by_id": self.user1.id,
            "payers": [{"user_id": self.user1.id, "amount_paid": 150.0}],
            "shares": [
                {"user_id": self.user1.id, "amount_owed": 0.0},
                {"user_id": self.user2.id, "amount_owed": 0.0},
                {"user_id": self.user3.id, "amount_owed": 0.0}
            ]
        }
        res = self.client.post('/api/expenses/', expense_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        group_res = self.client.get(f'/api/groups/{group.id}/')
        self.assertEqual(group_res.status_code, status.HTTP_200_OK)
        
        net_balances = group_res.data['net_balances']
        self.assertEqual(net_balances.get(self.user1.id, net_balances.get(str(self.user1.id))), 100.0)
        self.assertEqual(net_balances.get(self.user2.id, net_balances.get(str(self.user2.id))), -50.0)
        self.assertEqual(net_balances.get(self.user3.id, net_balances.get(str(self.user3.id))), -50.0)

        simplified = group_res.data['simplified_debts']
        self.assertEqual(len(simplified), 2)
