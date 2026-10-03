"""Splitting by shares: "they take two, I take one".

The fourth way to divide an expense, next to equally, exact amounts and percentages.
Shares are the shape of the answer when the ratio is obvious but the percentages aren't —
a room shared by two, a car taken by three of five people.

The number of shares is stored, not just the amounts it produced, so editing the expense
brings the ratio back instead of guessing it from rounded money.
"""
from unittest import mock

from rest_framework.test import APITestCase

from apps.users.models import UserProfile
from apps.groups.models import Group
from apps.expenses.models import Expense, ExpenseShare
from apps.notifications import push


class ShareSplitTests(APITestCase):
    def setUp(self):
        self.akash = UserProfile.objects.create(name="Akash", email="a@t.com", username="akash")
        self.rahul = UserProfile.objects.create(name="Rahul Kumar", email="r@t.com", username="rahul")
        self.anish = UserProfile.objects.create(name="Anish", email="n@t.com", username="anish")
        self.group = Group.objects.create(name="Flat", category="HOME", currency="₹")
        self.group.members.add(self.akash, self.rahul, self.anish)

        patcher = mock.patch.object(push, "queue")
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, units, amount=600, payer=None, description="Rent"):
        """units: {UserProfile: shares} — everyone listed is in the split."""
        return self.client.post("/api/expenses/", {
            "group_id": self.group.id, "description": description, "amount": amount,
            "category": "UTILITIES", "split_type": "SHARES",
            "created_by_id": self.akash.id, "actor_id": self.akash.id,
            "payers": [{"user_id": (payer or self.akash).id, "amount_paid": amount}],
            "shares": [{"user_id": user.id, "share_units": n} for user, n in units.items()],
        }, format="json")

    def owed(self, expense_id):
        return {s.user_id: float(s.amount_owed)
                for s in ExpenseShare.objects.filter(expense_id=expense_id)}

    def balances(self):
        detail = self.client.get(f"/api/groups/{self.group.id}/").data
        return {int(uid): round(value, 2) for uid, value in detail["net_balances"].items()}

    def test_two_shares_to_one_divides_the_bill_in_that_ratio(self):
        res = self.post({self.akash: 2, self.rahul: 1, self.anish: 1})
        self.assertEqual(res.status_code, 201, res.data)

        self.assertEqual(self.owed(res.data["id"]),
                         {self.akash.id: 300.0, self.rahul.id: 150.0, self.anish.id: 150.0})
        # Akash fronted the ₹600 and owes ₹300 of it, so he's ₹300 up
        self.assertEqual(self.balances(),
                         {self.akash.id: 300.0, self.rahul.id: -150.0, self.anish.id: -150.0})

    def test_the_shares_are_kept_so_an_edit_can_show_them_again(self):
        """The reason share_units exists: 2:1:1 can't be read back off ₹300/₹150/₹150."""
        expense_id = self.post({self.akash: 2, self.rahul: 1, self.anish: 1}).data["id"]

        shares = self.client.get(f"/api/expenses/{expense_id}/").data["shares"]
        self.assertEqual({s["user"]["id"]: s["share_units"] for s in shares},
                         {self.akash.id: 2.0, self.rahul.id: 1.0, self.anish.id: 1.0})

    def test_an_edit_can_change_the_ratio(self):
        expense_id = self.post({self.akash: 2, self.rahul: 1, self.anish: 1}).data["id"]

        res = self.client.put(f"/api/expenses/{expense_id}/", {
            "group_id": self.group.id, "description": "Rent", "amount": 600,
            "category": "UTILITIES", "split_type": "SHARES", "actor_id": self.akash.id,
            "payers": [{"user_id": self.akash.id, "amount_paid": 600}],
            "shares": [{"user_id": self.akash.id, "share_units": 1},
                       {"user_id": self.rahul.id, "share_units": 1},
                       {"user_id": self.anish.id, "share_units": 1}],
        }, format="json")
        self.assertEqual(res.status_code, 200, res.data)

        self.assertEqual(self.owed(expense_id),
                         {self.akash.id: 200.0, self.rahul.id: 200.0, self.anish.id: 200.0})
        self.assertEqual({s.user_id: s.share_units
                          for s in ExpenseShare.objects.filter(expense_id=expense_id)},
                         {self.akash.id: 1.0, self.rahul.id: 1.0, self.anish.id: 1.0})

    def test_the_shares_always_add_up_to_the_expense(self):
        """₹100 three ways can't be ₹99.99 — the group's balances would never settle."""
        res = self.post({self.akash: 1, self.rahul: 1, self.anish: 1}, amount=100)
        self.assertEqual(res.status_code, 201, res.data)

        owed = self.owed(res.data["id"])
        self.assertEqual(round(sum(owed.values()), 2), 100.0)
        self.assertEqual(sorted(owed.values()), [33.33, 33.33, 33.34])
        self.assertEqual(sum(self.balances().values()), 0.0)

    def test_nobody_on_a_share_is_refused_rather_than_divided_by_zero(self):
        res = self.post({self.akash: 0, self.rahul: 0, self.anish: 0})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Expense.objects.count(), 0)

    def test_a_negative_number_of_shares_is_refused(self):
        res = self.post({self.akash: 3, self.rahul: -1})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Expense.objects.count(), 0)

    def test_someone_can_be_left_out_with_no_shares(self):
        """Anish didn't take the car; he's in the group but owes nothing on this one."""
        res = self.post({self.akash: 1, self.rahul: 1, self.anish: 0}, amount=500)
        self.assertEqual(res.status_code, 201, res.data)

        self.assertEqual(self.owed(res.data["id"]),
                         {self.akash.id: 250.0, self.rahul.id: 250.0, self.anish.id: 0.0})
        self.assertEqual(self.balances()[self.anish.id], 0.0)

    def test_shares_work_alongside_two_people_paying(self):
        res = self.client.post("/api/expenses/", {
            "group_id": self.group.id, "description": "Weekend house", "amount": 900,
            "category": "OTHER", "split_type": "SHARES",
            "created_by_id": self.akash.id, "actor_id": self.akash.id,
            "payers": [{"user_id": self.akash.id, "amount_paid": 600},
                       {"user_id": self.rahul.id, "amount_paid": 300}],
            "shares": [{"user_id": self.akash.id, "share_units": 1},
                       {"user_id": self.rahul.id, "share_units": 1},
                       {"user_id": self.anish.id, "share_units": 2}],
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)

        # ₹900 at 1:1:2 is ₹225/₹225/₹450
        self.assertEqual(self.owed(res.data["id"]),
                         {self.akash.id: 225.0, self.rahul.id: 225.0, self.anish.id: 450.0})
        self.assertEqual(self.balances(),
                         {self.akash.id: 375.0, self.rahul.id: 75.0, self.anish.id: -450.0})

    def test_the_other_ways_of_splitting_still_behave(self):
        """share_units arriving on every share mustn't change EQUAL or PERCENTAGE."""
        equal = self.client.post("/api/expenses/", {
            "group_id": self.group.id, "description": "Dinner", "amount": 300,
            "category": "FOOD", "split_type": "EQUAL",
            "created_by_id": self.akash.id, "actor_id": self.akash.id,
            "payers": [{"user_id": self.akash.id, "amount_paid": 300}],
            "shares": [{"user_id": u.id} for u in (self.akash, self.rahul, self.anish)],
        }, format="json")
        self.assertEqual(equal.status_code, 201, equal.data)
        self.assertEqual(set(self.owed(equal.data["id"]).values()), {100.0})
        self.assertEqual(set(s.share_units for s in
                             ExpenseShare.objects.filter(expense_id=equal.data["id"])), {0.0})
