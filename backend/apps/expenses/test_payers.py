"""More than one person paying for the same expense.

The model always allowed it — a row per payer with their own amount — but nothing could
enter it. These pin the behaviour the form now relies on.
"""
from unittest import mock

from rest_framework.test import APITestCase

from apps.users.models import UserProfile
from apps.groups.models import Group
from apps.expenses.models import Expense
from apps.notifications import push


class MultiplePayerTests(APITestCase):
    def setUp(self):
        self.akash = UserProfile.objects.create(name="Akash", email="a@t.com", username="akash")
        self.rahul = UserProfile.objects.create(name="Rahul Kumar", email="r@t.com", username="rahul")
        self.anish = UserProfile.objects.create(name="Anish", email="n@t.com", username="anish")
        self.group = Group.objects.create(name="Dinners", category="OTHER", currency="₹")
        self.group.members.add(self.akash, self.rahul, self.anish)
        self.everyone = [self.akash.id, self.rahul.id, self.anish.id]

        self.sent = []
        patcher = mock.patch.object(push, "queue", side_effect=lambda msgs: self.sent.extend(msgs))
        patcher.start()
        self.addCleanup(patcher.stop)

    def expense(self, payers, amount=1200, shares=None, actor=None, split_type="EQUAL", extra=None):
        body = {
            "group_id": self.group.id, "description": "Dinner", "amount": amount,
            "category": "FOOD", "split_type": split_type,
            "created_by_id": (actor or self.akash).id, "actor_id": (actor or self.akash).id,
            "payers": [{"user_id": user.id, "amount_paid": paid} for user, paid in payers],
            "shares": [{"user_id": uid} for uid in (shares if shares is not None else self.everyone)],
        }
        body.update(extra or {})
        return self.client.post("/api/expenses/", body, format="json")

    def balances(self):
        detail = self.client.get(f"/api/groups/{self.group.id}/").data
        return {int(uid): round(value, 2) for uid, value in detail["net_balances"].items()}

    def test_two_people_paying_is_stored_and_balances_out(self):
        res = self.expense([(self.akash, 800), (self.rahul, 400)])
        self.assertEqual(res.status_code, 201, res.data)

        expense = Expense.objects.get()
        self.assertEqual(
            {p.user_id: float(p.amount_paid) for p in expense.payers.all()},
            {self.akash.id: 800.0, self.rahul.id: 400.0},
        )

        # Everyone's share is ₹400: Akash is up ₹400, Rahul is square, Anish owes ₹400
        self.assertEqual(self.balances(), {self.akash.id: 400.0, self.rahul.id: 0.0, self.anish.id: -400.0})

    def test_payers_that_do_not_add_up_are_refused(self):
        """What the form's live "still unaccounted for" line mirrors."""
        for label, payers in {
            "short": [(self.akash, 800), (self.rahul, 300)],
            "over": [(self.akash, 800), (self.rahul, 500)],
        }.items():
            with self.subTest(label):
                res = self.expense(payers)
                self.assertEqual(res.status_code, 400)
        self.assertEqual(Expense.objects.count(), 0)
        self.assertEqual(self.sent, [])

    def test_someone_can_pay_for_a_meal_they_are_not_in(self):
        res = self.expense(
            [(self.akash, 600), (self.rahul, 600)],
            shares=[self.rahul.id, self.anish.id],  # Akash paid but isn't eating
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(self.balances(), {self.akash.id: 600.0, self.rahul.id: 0.0, self.anish.id: -600.0})

    def test_both_payers_survive_an_edit(self):
        expense_id = self.expense([(self.akash, 800), (self.rahul, 400)]).data["id"]

        res = self.client.put(f"/api/expenses/{expense_id}/", {
            "group_id": self.group.id, "description": "Dinner", "amount": 1200, "category": "FOOD",
            "split_type": "EQUAL", "actor_id": self.akash.id,
            "payers": [{"user_id": self.akash.id, "amount_paid": 700},
                       {"user_id": self.rahul.id, "amount_paid": 500}],
            "shares": [{"user_id": uid} for uid in self.everyone],
        }, format="json")
        self.assertEqual(res.status_code, 200, res.data)

        expense = Expense.objects.get(id=expense_id)
        self.assertEqual(
            {p.user_id: float(p.amount_paid) for p in expense.payers.all()},
            {self.akash.id: 700.0, self.rahul.id: 500.0},
        )

    def test_the_notification_names_the_first_payer_and_counts_the_rest(self):
        self.expense([(self.akash, 800), (self.rahul, 400)], actor=self.anish)

        lines = {uid: payload["body"] for uid, payload in self.sent}
        # Each of them is told they were one of two payers, not that the other one paid
        self.assertEqual(lines[self.akash.id], "₹1,200 · you & 1 other paid · you get back ₹400")
        self.assertEqual(lines[self.rahul.id], "₹1,200 · you & 1 other paid · your share ₹400")
        # Anish entered it, so he hears nothing; a bystander would read "Akash & 1 other paid"
        self.assertNotIn(self.anish.id, lines)

        self.sent.clear()
        self.expense([(self.akash, 800), (self.rahul, 400)], actor=self.akash, shares=self.everyone)
        self.assertEqual(
            {uid: payload["body"] for uid, payload in self.sent}[self.anish.id],
            "₹1,200 · Akash & 1 other paid · your share ₹400",
        )

    def test_an_itemised_bill_rounds_to_whoever_paid_most(self):
        res = self.expense(
            [(self.rahul, 40), (self.akash, 60)],
            amount=100,
            split_type="ITEMS",
            shares=[],
            extra={"items": [{"name": "Coffee", "price": 100, "assigned_member_ids": self.everyone}]},
        )
        self.assertEqual(res.status_code, 201, res.data)

        shares = {s.user_id: float(s.amount_owed) for s in Expense.objects.get(id=res.data["id"]).shares.all()}
        self.assertAlmostEqual(sum(shares.values()), 100.0, places=2)
        self.assertEqual(shares[self.akash.id], 33.34)   # paid the most, so carries the extra paisa
        self.assertEqual(shares[self.rahul.id], 33.33)
        self.assertEqual(shares[self.anish.id], 33.33)
