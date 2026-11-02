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


class GroupDetailQueryTests(APITestCase):
    """The group page must not run more queries as the group gains expenses."""

    def setUp(self):
        self.users = [UserProfile.objects.create(name=f"U{i}", email=f"u{i}@test.com") for i in range(4)]
        self.group = Group.objects.create(name="Groceries", category="HOME")
        self.group.members.add(*self.users)

    def _add_expenses(self, n):
        from apps.expenses.models import Expense, ExpensePayer, ExpenseShare, Settlement
        for i in range(n):
            e = Expense.objects.create(group=self.group, description=f"Order {i}", amount=40,
                                       created_by=self.users[0], updated_by=self.users[1])
            ExpensePayer.objects.create(expense=e, user=self.users[i % 4], amount_paid=40)
            for u in self.users:
                ExpenseShare.objects.create(expense=e, user=u, amount_owed=10)
        Settlement.objects.create(group=self.group, payer=self.users[1], payee=self.users[0],
                                  amount=5, created_by=self.users[1])

    def _queries_for(self, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return len(ctx.captured_queries), res

    def test_query_count_does_not_grow_with_expenses(self):
        url = f'/api/groups/{self.group.id}/?user_id={self.users[0].id}'
        self._add_expenses(3)
        few, _ = self._queries_for(url)
        self._add_expenses(30)
        many, res = self._queries_for(url)
        self.assertEqual(few, many)
        self.assertEqual(len(res.data['expenses']), 33)
        self.assertEqual(len(res.data['expenses'][0]['shares']), 4)

    def test_expense_list_query_count_does_not_grow(self):
        self._add_expenses(3)
        few, _ = self._queries_for('/api/expenses/')
        self._add_expenses(30)
        many, _ = self._queries_for('/api/expenses/')
        self.assertEqual(few, many)

    def test_lite_leaves_out_the_lists_but_keeps_balances(self):
        self._add_expenses(4)
        _, full = self._queries_for(f'/api/groups/{self.group.id}/')
        _, lite = self._queries_for(f'/api/groups/{self.group.id}/?lite=1')
        self.assertNotIn('expenses', lite.data)
        self.assertNotIn('settlements', lite.data)
        self.assertEqual(lite.data['net_balances'], full.data['net_balances'])
        self.assertEqual(lite.data['total_spending'], full.data['total_spending'])
