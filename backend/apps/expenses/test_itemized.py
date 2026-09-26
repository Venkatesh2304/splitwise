import json
from unittest import mock

from rest_framework.test import APITestCase

from apps.users.models import UserProfile
from apps.groups.models import Group
from apps.expenses.models import Expense
from apps.expenses.grocery_engine.split_engine import GrocerySplitEngine
from apps.notifications import push


class ItemisedExpenseTests(APITestCase):
    """A restaurant bill: starters everyone shared, cocktails one person drank, plus tax."""

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

    def bill(self, items=None, amount=1000, payer=None, actor=None, description="Dinner at Bakeroven"):
        payer = payer or self.rahul
        return {
            "group_id": self.group.id,
            "description": description,
            "amount": amount,
            "category": "FOOD",
            "split_type": "ITEMS",
            "created_by_id": payer.id,
            "actor_id": (actor or payer).id,
            "payers": [{"user_id": payer.id, "amount_paid": amount}],
            "shares": [],
            "items": items if items is not None else [
                {"name": "Starters", "price": 300, "assigned_member_ids": self.everyone},
                {"name": "Cocktails", "price": 500, "assigned_member_ids": [self.anish.id]},
            ],
        }

    def shares_of(self, expense_id):
        expense = Expense.objects.get(id=expense_id)
        return {s.user_id: float(s.amount_owed) for s in expense.shares.all()}

    def test_items_are_charged_to_their_people_and_tax_follows_the_items(self):
        res = self.client.post("/api/expenses/", self.bill(), format="json")
        self.assertEqual(res.status_code, 201, res.data)

        # Starters ₹300 three ways = ₹100 each; Anish also has ₹500 of cocktails.
        # ₹200 of tax spread over those subtotals: ₹25, ₹25, ₹150.
        shares = self.shares_of(res.data["id"])
        self.assertEqual(shares, {self.akash.id: 125.0, self.rahul.id: 125.0, self.anish.id: 750.0})
        self.assertAlmostEqual(sum(shares.values()), 1000.0, places=2)

    def test_the_rounding_difference_goes_to_whoever_paid(self):
        res = self.client.post("/api/expenses/", self.bill(
            amount=100,
            items=[{"name": "Coffee", "price": 100, "assigned_member_ids": self.everyone}],
            payer=self.akash,
        ), format="json")

        shares = self.shares_of(res.data["id"])
        self.assertAlmostEqual(sum(shares.values()), 100.0, places=2)
        self.assertEqual(shares[self.rahul.id], 33.33)
        self.assertEqual(shares[self.anish.id], 33.33)
        self.assertEqual(shares[self.akash.id], 33.34)  # Akash paid, so he carries the extra paisa

    def test_a_grocery_order_and_a_typed_bill_split_identically(self):
        """Both go through split_items; if anyone re-inlines the maths, this fails."""
        items = [
            {"name": "Starters", "price": 300, "assigned_member_ids": self.everyone},
            {"name": "Cocktails", "price": 500, "assigned_member_ids": [self.anish.id]},
        ]
        typed = self.client.post("/api/expenses/", self.bill(items=items), format="json")

        ordered = GrocerySplitEngine.process_split(
            platform_name="Blinkit", group_id=self.group.id, buyer_id=self.rahul.id,
            order_id="9001", total_amount=1000, split_mode="ITEMIZED", actor_id=self.rahul.id,
            item_splits_data=[dict(item, split_type="SPECIFIC") for item in items],
        )

        self.assertEqual(self.shares_of(typed.data["id"]), self.shares_of(ordered["expense_id"]))

    def test_the_items_are_stored_and_it_is_not_mistaken_for_an_order(self):
        res = self.client.post("/api/expenses/", self.bill(), format="json")
        notes = json.loads(Expense.objects.get(id=res.data["id"]).notes)

        self.assertNotIn("platform", notes)  # what marks an expense as a Blinkit/Swiggy order
        self.assertEqual([i["name"] for i in notes["items"]], ["Starters", "Cocktails"])
        starters, cocktails = notes["items"]
        self.assertEqual(starters["split_type"], "ALL")          # everyone had them
        self.assertEqual(cocktails["split_type"], "SPECIFIC")
        self.assertEqual(cocktails["assigned_names"], ["Anish"])

    def test_it_can_be_edited_as_items_and_switched_back_to_an_even_split(self):
        expense_id = self.client.post("/api/expenses/", self.bill(), format="json").data["id"]

        # Rahul had a cocktail too
        edit = self.bill(items=[
            {"name": "Starters", "price": 300, "assigned_member_ids": self.everyone},
            {"name": "Cocktails", "price": 500, "assigned_member_ids": [self.anish.id, self.rahul.id]},
        ], actor=self.akash)
        res = self.client.put(f"/api/expenses/{expense_id}/", edit, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["id"], expense_id)

        shares = self.shares_of(expense_id)
        self.assertEqual(shares, {self.akash.id: 125.0, self.rahul.id: 437.5, self.anish.id: 437.5})

        # Switching away from items clears them, so nothing stale describes the expense
        plain = {**self.bill(), "split_type": "EQUAL", "items": None,
                 "shares": [{"user_id": uid} for uid in self.everyone]}
        plain.pop("items")
        res = self.client.put(f"/api/expenses/{expense_id}/", plain, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Expense.objects.get(id=expense_id).notes, '')
        self.assertEqual(sorted(self.shares_of(expense_id).values()), [333.33, 333.33, 333.34])

    def test_bad_bills_are_refused(self):
        stranger = UserProfile.objects.create(name="Stranger", email="s@t.com", username="stranger")
        cases = {
            "no items": [],
            "unassigned": [{"name": "Starters", "price": 300, "assigned_member_ids": []}],
            "outsider": [{"name": "Starters", "price": 300, "assigned_member_ids": [stranger.id]}],
            "more than the bill": [{"name": "Starters", "price": 3000, "assigned_member_ids": self.everyone}],
            "negative": [{"name": "Discount", "price": -50, "assigned_member_ids": self.everyone}],
        }
        for label, items in cases.items():
            with self.subTest(label):
                res = self.client.post("/api/expenses/", self.bill(items=items), format="json")
                self.assertEqual(res.status_code, 400, f"{label} should be refused")
        self.assertEqual(Expense.objects.count(), 0)
        self.assertEqual(self.sent, [])

    def test_everyone_is_told_their_own_share(self):
        self.client.post("/api/expenses/", self.bill(actor=self.rahul), format="json")

        lines = {uid: payload["body"] for uid, payload in self.sent}
        self.assertEqual(lines[self.akash.id], "₹1,000 · Rahul paid · your share ₹125")
        self.assertEqual(lines[self.anish.id], "₹1,000 · Rahul paid · your share ₹750")
        self.assertNotIn(self.rahul.id, lines)  # he entered it
