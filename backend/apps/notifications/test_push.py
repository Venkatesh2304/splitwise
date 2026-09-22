import json
import tempfile
from unittest import mock

from django.test import override_settings
from rest_framework.test import APITestCase
from pywebpush import WebPushException

from apps.users.models import UserProfile
from apps.groups.models import Group
from apps.expenses.models import Expense, Settlement
from apps.expenses.grocery_engine.split_engine import GrocerySplitEngine
from apps.notifications import events, keys, push
from apps.notifications.models import PushSubscription


class PushTestBase(APITestCase):
    def setUp(self):
        self.akash = UserProfile.objects.create(name="Akash", email="a@t.com", username="akash")
        self.rahul = UserProfile.objects.create(name="Rahul Kumar", email="r@t.com", username="rahul")
        self.anish = UserProfile.objects.create(name="Anish", email="n@t.com", username="anish")
        self.giri = UserProfile.objects.create(name="Giri", email="g@t.com", username="giri")
        self.group = Group.objects.create(name="Groceries 🛒", category="HOME", currency="₹")
        self.group.members.add(self.akash, self.rahul, self.anish, self.giri)

        # Capture what would be sent instead of talking to a push service
        self.sent = []
        patcher = mock.patch.object(push, "queue", side_effect=lambda msgs: self.sent.extend(msgs))
        patcher.start()
        self.addCleanup(patcher.stop)

    def to(self, user):
        return [payload for uid, payload in self.sent if uid == user.id]

    def recipients(self):
        return sorted({uid for uid, _ in self.sent})

    def expense_payload(self, amount, payer, members, split_type="EQUAL", values=None, actor=None, **extra):
        values = values or {}
        shares = []
        for m in members:
            share = {"user_id": m.id}
            if split_type == "EXACT":
                share["amount_owed"] = values[m.id]
            elif split_type == "PERCENTAGE":
                share["percentage"] = values[m.id]
            shares.append(share)
        payload = {
            "group_id": self.group.id,
            "description": "Dinner",
            "amount": amount,
            "category": "FOOD",
            "split_type": split_type,
            "created_by_id": (actor or payer).id,
            "payers": [{"user_id": payer.id, "amount_paid": amount}],
            "shares": shares,
            "actor_id": (actor or payer).id,
        }
        payload.update(extra)
        return payload

    def split_order(self, order_id, assignments, buyer, actor, total=None):
        """assignments: list of (item name, price, [members])"""
        items = [
            {"name": name, "price": price, "split_type": "SPECIFIC", "assigned_member_ids": [m.id for m in members]}
            for name, price, members in assignments
        ]
        return GrocerySplitEngine.process_split(
            platform_name="Blinkit",
            group_id=self.group.id,
            buyer_id=buyer.id,
            order_id=order_id,
            total_amount=total if total is not None else sum(p for _, p, _ in assignments),
            split_mode="ITEMIZED",
            item_splits_data=items,
            actor_id=actor.id,
        )


class ExpenseAddedTests(PushTestBase):
    def test_involved_people_except_actor_are_notified(self):
        res = self.client.post("/api/expenses/", self.expense_payload(300, self.akash, [self.akash, self.rahul, self.anish]), format="json")
        self.assertEqual(res.status_code, 201)

        # Akash made it, Giri has no share
        self.assertEqual(self.recipients(), sorted([self.rahul.id, self.anish.id]))
        msg = self.to(self.rahul)[0]
        self.assertEqual(msg["title"], "Akash added “Dinner”")
        self.assertEqual(msg["body"], "₹300 · Akash paid · your share ₹100")
        self.assertEqual(msg["tag"], f"expense-{res.data['id']}")
        self.assertEqual(msg["url"], f"/?group={self.group.id}&expense={res.data['id']}")

    def test_payer_who_did_not_enter_it_hears_what_they_get_back(self):
        payload = self.expense_payload(300, self.rahul, [self.akash, self.rahul, self.anish], actor=self.akash)
        self.client.post("/api/expenses/", payload, format="json")

        self.assertEqual(self.to(self.rahul)[0]["body"], "₹300 · you paid · you get back ₹200")
        self.assertEqual(self.to(self.anish)[0]["body"], "₹300 · Rahul paid · your share ₹100")
        self.assertEqual(self.to(self.akash), [])

    def test_actor_defaults_to_author_when_client_sends_none(self):
        payload = self.expense_payload(300, self.akash, [self.akash, self.rahul])
        del payload["actor_id"]
        self.client.post("/api/expenses/", payload, format="json")
        self.assertEqual(self.recipients(), [self.rahul.id])

    def test_grocery_split_skips_zero_shares(self):
        self.split_order("ORD1", [("Milk", 100.0, [self.akash, self.rahul]), ("Eggs", 60.0, [self.rahul])], buyer=self.akash, actor=self.akash)

        self.assertEqual(self.recipients(), [self.rahul.id])  # Anish/Giri have ₹0 shares
        msg = self.to(self.rahul)[0]
        self.assertEqual(msg["title"], "🛒 Akash split a Blinkit order")
        self.assertEqual(msg["body"], "₹160 · Akash paid · your share ₹110")
        self.assertEqual(msg["tag"], "order-ORD1")


class ExpenseEditedTests(PushTestBase):
    def create(self, **kwargs):
        res = self.client.post("/api/expenses/", self.expense_payload(**kwargs), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.sent.clear()
        return res.data["id"]

    def test_edit_reports_share_change_to_everyone_before_or_after(self):
        exp_id = self.create(amount=300, payer=self.akash, members=[self.akash, self.rahul, self.anish])

        payload = self.expense_payload(300, self.akash, [self.akash, self.rahul, self.giri], split_type="EXACT",
                                       values={self.akash.id: 100, self.rahul.id: 150, self.giri.id: 50}, actor=self.anish)
        res = self.client.put(f"/api/expenses/{exp_id}/", payload, format="json")
        self.assertEqual(res.status_code, 200, res.data)

        # Akash (payer) + Rahul + Anish (removed, but he's the actor) + Giri (added)
        self.assertEqual(self.recipients(), sorted([self.akash.id, self.rahul.id, self.giri.id]))
        self.assertEqual(self.to(self.rahul)[0]["title"], "Anish updated “Dinner”")
        self.assertEqual(self.to(self.rahul)[0]["body"], "your share ₹100 → ₹150 · total ₹300")
        self.assertEqual(self.to(self.giri)[0]["body"], "your share ₹0 → ₹50 · total ₹300")
        self.assertEqual(self.to(self.akash)[0]["body"], "your share unchanged (₹100) · total ₹300")

    def test_removed_person_is_told(self):
        exp_id = self.create(amount=300, payer=self.akash, members=[self.akash, self.rahul, self.anish])
        payload = self.expense_payload(400, self.akash, [self.akash, self.rahul], actor=self.akash)
        self.client.put(f"/api/expenses/{exp_id}/", payload, format="json")
        self.assertEqual(self.to(self.anish)[0]["body"], "your share ₹100 → ₹0 · total ₹300 → ₹400")

    def test_update_recalculates_keeps_id_and_author(self):
        exp_id = self.create(amount=300, payer=self.akash, members=[self.akash, self.rahul, self.anish])

        payload = self.expense_payload(200, self.rahul, [self.akash, self.rahul], split_type="PERCENTAGE",
                                       values={self.akash.id: 25, self.rahul.id: 75}, actor=self.anish)
        payload["created_by_id"] = self.anish.id  # must not change the author
        res = self.client.put(f"/api/expenses/{exp_id}/", payload, format="json")
        self.assertEqual(res.status_code, 200, res.data)

        expense = Expense.objects.get(id=exp_id)
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(float(expense.amount), 200.0)
        self.assertEqual(expense.split_type, "PERCENTAGE")
        self.assertEqual({s.user_id: float(s.amount_owed) for s in expense.shares.all()}, {self.akash.id: 50.0, self.rahul.id: 150.0})
        self.assertEqual([(p.user_id, float(p.amount_paid)) for p in expense.payers.all()], [(self.rahul.id, 200.0)])
        self.assertEqual(expense.created_by, self.akash)
        self.assertEqual(expense.updated_by, self.anish)
        self.assertIsNotNone(expense.updated_at)
        self.assertEqual(res.data["updated_by"]["id"], self.anish.id)

    def test_invalid_edit_is_rejected_and_changes_nothing(self):
        exp_id = self.create(amount=300, payer=self.akash, members=[self.akash, self.rahul, self.anish])
        payload = self.expense_payload(300, self.akash, [self.akash, self.rahul], split_type="EXACT",
                                       values={self.akash.id: 100, self.rahul.id: 100})
        res = self.client.put(f"/api/expenses/{exp_id}/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Expense.objects.get(id=exp_id).shares.count(), 3)
        self.assertEqual(self.sent, [])

    def test_grocery_split_cannot_be_edited_through_the_form(self):
        res = self.split_order("ORD9", [("Milk", 100.0, [self.akash, self.rahul])], buyer=self.akash, actor=self.akash)
        payload = self.expense_payload(100, self.akash, [self.akash, self.rahul])
        res = self.client.put(f"/api/expenses/{res['expense_id']}/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Re-split", str(res.data))

    def test_resplit_is_an_edit_and_keeps_its_place(self):
        first = self.split_order("ORD2", [("Milk", 100.0, [self.akash, self.rahul]), ("Eggs", 80.0, [self.anish])], buyer=self.akash, actor=self.akash)
        original = Expense.objects.get(id=first["expense_id"])
        self.sent.clear()

        second = self.split_order("ORD2", [("Milk", 100.0, [self.akash, self.rahul, self.anish]), ("Eggs", 80.0, [self.rahul])],
                                  buyer=self.akash, actor=self.rahul)

        resplit = Expense.objects.get(id=second["expense_id"])
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(resplit.created_at, original.created_at)
        self.assertEqual(resplit.date, original.date)
        self.assertEqual(resplit.updated_by, self.rahul)

        # Rahul re-split it: Akash (payer) and Anish hear about it
        self.assertEqual(self.recipients(), sorted([self.akash.id, self.anish.id]))
        msg = self.to(self.anish)[0]
        self.assertEqual(msg["title"], "🛒 Rahul updated “Blinkit Order #ORD2”")
        self.assertEqual(msg["body"], "your share ₹80 → ₹33.33 · total ₹180")
        self.assertEqual(msg["tag"], "order-ORD2")


class DeleteAndSettlementTests(PushTestBase):
    def test_delete_expense(self):
        res = self.client.post("/api/expenses/", self.expense_payload(300, self.akash, [self.akash, self.rahul, self.anish]), format="json")
        self.sent.clear()

        self.client.delete(f"/api/expenses/{res.data['id']}/?actor_id={self.anish.id}")

        self.assertEqual(self.recipients(), sorted([self.akash.id, self.rahul.id]))
        self.assertEqual(self.to(self.rahul)[0]["title"], "Anish deleted “Dinner”")
        self.assertEqual(self.to(self.rahul)[0]["body"], "₹300 · your share was ₹100")
        self.assertEqual(self.to(self.akash)[0]["body"], "₹300 · you were getting back ₹200")
        self.assertEqual(self.to(self.akash)[0]["url"], f"/?group={self.group.id}")

    def test_remove_split_notifies_as_delete_with_order_tag(self):
        self.split_order("ORD3", [("Milk", 100.0, [self.akash, self.rahul])], buyer=self.akash, actor=self.akash)
        self.sent.clear()
        GrocerySplitEngine.remove_split("ORD3", actor_id=self.akash.id)
        self.assertEqual(self.recipients(), [self.rahul.id])
        self.assertEqual(self.to(self.rahul)[0]["tag"], "order-ORD3")
        self.assertEqual(Expense.objects.count(), 0)

    def settle(self, payer, payee, amount, actor, notes="Payment settlement via Splitwise"):
        return self.client.post("/api/settlements/", {
            "group_id": self.group.id, "payer_id": payer.id, "payee_id": payee.id,
            "amount": amount, "notes": notes, "actor_id": actor.id,
        }, format="json")

    def test_settlement_by_payer_tells_payee_only(self):
        res = self.settle(self.rahul, self.akash, 500, actor=self.rahul)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.recipients(), [self.akash.id])
        self.assertEqual(self.to(self.akash)[0]["title"], "💸 Rahul paid you ₹500")
        self.assertEqual(self.to(self.akash)[0]["body"], "Groceries 🛒")
        self.assertEqual(Settlement.objects.get().created_by, self.rahul)
        self.assertEqual(res.data["created_by"]["id"], self.rahul.id)

    def test_settlement_recorded_by_someone_else_tells_both(self):
        self.settle(self.rahul, self.akash, 500, actor=self.anish, notes="GPay")
        self.assertEqual(self.to(self.akash)[0]["title"], "💸 Rahul paid you ₹500")
        self.assertEqual(self.to(self.rahul)[0]["title"], "💸 You paid Akash ₹500")
        self.assertEqual(self.to(self.rahul)[0]["body"], "GPay · recorded by Anish · Groceries 🛒")

    def test_settlement_delete(self):
        res = self.settle(self.rahul, self.akash, 500, actor=self.rahul)
        self.sent.clear()
        self.client.delete(f"/api/settlements/{res.data['id']}/?actor_id={self.akash.id}")
        self.assertEqual(self.recipients(), [self.rahul.id])
        self.assertEqual(self.to(self.rahul)[0]["title"], "Akash deleted a settle-up")
        self.assertEqual(self.to(self.rahul)[0]["body"], "You paid Akash ₹500 · Groceries 🛒")


class FormattingTests(APITestCase):
    def test_money(self):
        self.assertEqual(events.money(774), "₹774")
        self.assertEqual(events.money(120.31), "₹120.31")
        self.assertEqual(events.money(120000), "₹1,20,000")
        self.assertEqual(events.money(12345678.5), "₹1,23,45,678.50")
        self.assertEqual(events.money(1234, "$"), "$1,234")


class DeliveryTests(APITestCase):
    """Subscriptions, key handling and the actual send path (push service mocked)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(PUSH_KEYS_DIR=self.tmp.name, PUSH_SEND_INLINE=True)
        override.enable()
        self.addCleanup(override.disable)
        self.akash = UserProfile.objects.create(name="Akash", email="a@t.com", username="akash")
        self.rahul = UserProfile.objects.create(name="Rahul", email="r@t.com", username="rahul")

    def subscribe(self, user, endpoint="https://fcm.googleapis.com/fcm/send/abc"):
        return self.client.post("/api/push/subscribe/", {
            "user_id": user.id,
            "subscription": {"endpoint": endpoint, "keys": {"p256dh": "BPkey", "auth": "authkey"}},
        }, format="json")

    def test_public_key_needs_setup(self):
        self.assertEqual(self.client.get("/api/push/public_key/").status_code, 503)
        keys.ensure()
        res = self.client.get("/api/push/public_key/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["public_key"]), 87)  # 65-byte uncompressed P-256 point, base64url

    def test_ensure_never_replaces_the_key(self):
        self.assertTrue(keys.ensure())
        first = keys.load().public_key
        self.assertFalse(keys.ensure("mailto:v@example.com"))
        self.assertEqual(keys.load().public_key, first)
        self.assertEqual(keys.load().subject, "mailto:v@example.com")

    def test_subscribing_same_device_as_another_user_moves_it(self):
        self.assertEqual(self.subscribe(self.akash).status_code, 200)
        self.assertEqual(self.subscribe(self.rahul).status_code, 200)
        self.assertEqual(PushSubscription.objects.count(), 1)
        self.assertEqual(PushSubscription.objects.get().user, self.rahul)

    def test_rejects_bad_subscriptions(self):
        self.assertEqual(self.subscribe(self.akash, endpoint="http://insecure").status_code, 400)
        res = self.client.post("/api/push/subscribe/", {"user_id": "nope", "subscription": {}}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_unsubscribe(self):
        self.subscribe(self.akash)
        self.client.post("/api/push/unsubscribe/", {"endpoint": "https://fcm.googleapis.com/fcm/send/abc"}, format="json")
        self.assertEqual(PushSubscription.objects.count(), 0)

    def test_expense_reaches_subscribed_device_after_commit(self):
        keys.ensure()
        self.subscribe(self.rahul)
        group = Group.objects.create(name="Trip", currency="₹")
        group.members.add(self.akash, self.rahul)

        with mock.patch.object(push, "webpush") as webpush, self.captureOnCommitCallbacks(execute=True):
            self.client.post("/api/expenses/", {
                "group_id": group.id, "description": "Cab", "amount": 200, "split_type": "EQUAL",
                "created_by_id": self.akash.id, "actor_id": self.akash.id,
                "payers": [{"user_id": self.akash.id, "amount_paid": 200}],
                "shares": [{"user_id": self.akash.id}, {"user_id": self.rahul.id}],
            }, format="json")

        self.assertEqual(webpush.call_count, 1)
        kwargs = webpush.call_args.kwargs
        self.assertEqual(kwargs["subscription_info"]["endpoint"], "https://fcm.googleapis.com/fcm/send/abc")
        self.assertEqual(json.loads(kwargs["data"])["body"], "₹200 · Akash paid · your share ₹100")
        self.assertIsNotNone(PushSubscription.objects.get().last_success_at)

    def test_gone_subscription_is_deleted_other_errors_kept(self):
        keys.ensure()
        self.subscribe(self.rahul)

        def failing(status_code):
            return WebPushException("failed", response=mock.Mock(status_code=status_code))

        with mock.patch.object(push, "webpush", side_effect=failing(500)):
            push.deliver([(self.rahul.id, {"title": "x"})])
        self.assertEqual(PushSubscription.objects.count(), 1)

        with mock.patch.object(push, "webpush", side_effect=failing(410)):
            push.deliver([(self.rahul.id, {"title": "x"})])
        self.assertEqual(PushSubscription.objects.count(), 0)

    def test_test_endpoint_reports_devices(self):
        keys.ensure()
        self.subscribe(self.akash)
        with mock.patch.object(push, "webpush") as webpush:
            res = self.client.post("/api/push/test/", {"user_id": self.akash.id}, format="json")
        self.assertEqual(res.data, {"sent": 1, "devices": 1})
        self.assertEqual(json.loads(webpush.call_args.kwargs["data"])["tag"], "test")
