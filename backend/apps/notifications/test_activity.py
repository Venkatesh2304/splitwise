from unittest import mock

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.users.models import UserProfile
from apps.groups.models import Group, GroupMember
from apps.expenses.models import Expense
from apps.expenses.grocery_engine.split_engine import GrocerySplitEngine
from apps.notifications import activity, push
from apps.notifications.models import ActivityEvent


class ActivityTestBase(APITestCase):
    def setUp(self):
        self.akash = UserProfile.objects.create(name="Akash", email="a@t.com", username="akash")
        self.rahul = UserProfile.objects.create(name="Rahul Kumar", email="r@t.com", username="rahul")
        self.anish = UserProfile.objects.create(name="Anish", email="n@t.com", username="anish")
        self.group = Group.objects.create(name="Groceries 🛒", category="HOME", currency="₹")
        self.group.members.add(self.akash, self.rahul, self.anish)

        self.sent = []
        patcher = mock.patch.object(push, "queue", side_effect=lambda msgs: self.sent.extend(msgs))
        patcher.start()
        self.addCleanup(patcher.stop)

    def add_expense(self, description="Dinner", amount=300, payer=None, members=None, actor=None):
        payer = payer or self.rahul
        members = members or [self.akash, self.rahul, self.anish]
        actor = actor or payer
        res = self.client.post("/api/expenses/", {
            "group_id": self.group.id, "description": description, "amount": amount,
            "category": "FOOD", "split_type": "EQUAL", "created_by_id": payer.id, "actor_id": actor.id,
            "payers": [{"user_id": payer.id, "amount_paid": amount}],
            "shares": [{"user_id": m.id} for m in members],
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        return res.data["id"]

    def events_for(self, user):
        return activity.serialize(activity.for_user(self.group.id, user.id), user.id)


class ActivityRecordingTests(ActivityTestBase):
    def test_an_added_expense_is_recorded_for_everyone_but_the_actor(self):
        expense_id = self.add_expense()

        event = ActivityEvent.objects.get()
        self.assertEqual(event.kind, ActivityEvent.EXPENSE_ADDED)
        self.assertEqual(event.title, "Rahul added “Dinner”")
        self.assertEqual(event.actor, self.rahul)
        self.assertEqual(event.expense_id, expense_id)
        self.assertEqual(event.url, f"/?group={self.group.id}&expense={expense_id}")
        self.assertEqual(sorted(event.lines), sorted([str(self.akash.id), str(self.anish.id)]))
        self.assertFalse(event.concerns(self.rahul.id))
        self.assertEqual(event.line_for(self.akash.id), "₹300 · Rahul paid · your share ₹100")

    def test_the_stored_line_is_the_text_that_was_notified(self):
        """The strip and the notification must never word the same change differently."""
        self.add_expense()
        event = ActivityEvent.objects.get()
        for user_id, payload in self.sent:
            self.assertEqual(event.line_for(user_id), payload["body"])
            self.assertEqual(event.title, payload["title"])

    def test_edit_and_settlement_and_their_deletions_are_recorded(self):
        expense_id = self.add_expense()

        self.client.put(f"/api/expenses/{expense_id}/", {
            "group_id": self.group.id, "description": "Dinner", "amount": 600, "category": "FOOD",
            "split_type": "EQUAL", "actor_id": self.rahul.id,
            "payers": [{"user_id": self.rahul.id, "amount_paid": 600}],
            "shares": [{"user_id": self.akash.id}, {"user_id": self.rahul.id}, {"user_id": self.anish.id}],
        }, format="json")
        settlement = self.client.post("/api/settlements/", {
            "group_id": self.group.id, "payer_id": self.anish.id, "payee_id": self.akash.id,
            "amount": 100, "actor_id": self.anish.id,
        }, format="json")
        self.client.delete(f"/api/settlements/{settlement.data['id']}/?actor_id={self.anish.id}")
        self.client.delete(f"/api/expenses/{expense_id}/?actor_id={self.rahul.id}")

        kinds = list(ActivityEvent.objects.order_by('id').values_list('kind', flat=True))
        self.assertEqual(kinds, [
            ActivityEvent.EXPENSE_ADDED, ActivityEvent.EXPENSE_EDITED,
            ActivityEvent.SETTLEMENT_RECORDED, ActivityEvent.SETTLEMENT_DELETED,
            ActivityEvent.EXPENSE_DELETED,
        ])
        edited = ActivityEvent.objects.get(kind=ActivityEvent.EXPENSE_EDITED)
        self.assertEqual(edited.line_for(self.akash.id), "your share ₹100 → ₹200 · total ₹300 → ₹600")
        # A settlement is stored naming both people, not "You paid ..." from one side
        recorded = ActivityEvent.objects.get(kind=ActivityEvent.SETTLEMENT_RECORDED)
        self.assertEqual(recorded.title, "💸 Anish paid Akash ₹100")

    def test_a_deletion_outlives_the_expense_it_describes(self):
        expense_id = self.add_expense(description="Pizza night", amount=1600)
        self.client.delete(f"/api/expenses/{expense_id}/?actor_id={self.rahul.id}")

        self.assertFalse(Expense.objects.filter(id=expense_id).exists())
        event = ActivityEvent.objects.get(kind=ActivityEvent.EXPENSE_DELETED)
        self.assertEqual(event.title, "Rahul deleted “Pizza night”")
        # Akash is first in the split, so he carries the rounding remainder of 1600/3
        self.assertEqual(event.line_for(self.akash.id), "₹1,600 · your share was ₹533.34")
        self.assertEqual(event.line_for(self.anish.id), "₹1,600 · your share was ₹533.33")

    def test_a_change_nobody_else_is_in_records_nothing(self):
        self.add_expense(description="Rahul's headphones", amount=2499, payer=self.rahul, members=[self.rahul])
        self.assertEqual(ActivityEvent.objects.count(), 0)

    def test_grocery_resplit_is_recorded_as_an_edit(self):
        for coffee_drinker in (self.akash, self.anish):
            GrocerySplitEngine.process_split(
                platform_name="Blinkit", group_id=self.group.id, buyer_id=self.rahul.id,
                order_id="551", total_amount=400, split_mode="ITEMIZED", actor_id=self.rahul.id,
                item_splits_data=[{"name": "Cold coffee", "price": 400, "split_type": "SPECIFIC",
                                   "assigned_member_ids": [coffee_drinker.id]}])

        kinds = list(ActivityEvent.objects.order_by('id').values_list('kind', flat=True))
        self.assertEqual(kinds, [ActivityEvent.EXPENSE_ADDED, ActivityEvent.EXPENSE_EDITED])
        edit = ActivityEvent.objects.get(kind=ActivityEvent.EXPENSE_EDITED)
        self.assertEqual(edit.line_for(self.akash.id), "your share ₹400 → ₹0 · total ₹400")


class UnseenTests(ActivityTestBase):
    def unseen(self, user):
        return activity.unseen_count(self.group.id, user.id)

    def test_your_own_changes_are_never_unseen(self):
        self.add_expense(actor=self.akash, payer=self.akash)
        self.assertEqual(self.unseen(self.akash), 0)
        self.assertEqual(self.unseen(self.rahul), 1)

    def test_expenses_you_are_not_in_are_not_counted(self):
        self.add_expense(description="Just those two", payer=self.rahul, members=[self.rahul, self.anish])
        self.assertEqual(self.unseen(self.akash), 0)
        self.assertEqual(self.unseen(self.anish), 1)

    def test_marking_seen_clears_the_count_and_returns_the_previous_mark(self):
        self.add_expense()
        self.assertEqual(self.unseen(self.akash), 2 - 1)  # one event so far

        before = activity.baseline_for(self.group.id, self.akash.id)
        res = self.client.post(f"/api/groups/{self.group.id}/seen/", {"user_id": self.akash.id}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["previous_seen_at"], before)
        self.assertEqual(self.unseen(self.akash), 0)

        # Anything after the mark counts again
        self.add_expense(description="Cab")
        self.assertEqual(self.unseen(self.akash), 1)

    def test_seen_is_idempotent_and_needs_a_user(self):
        first = self.client.post(f"/api/groups/{self.group.id}/seen/", {"user_id": self.akash.id}, format="json")
        second = self.client.post(f"/api/groups/{self.group.id}/seen/", {"user_id": self.akash.id}, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertGreaterEqual(second.data["previous_seen_at"], first.data["previous_seen_at"])
        self.assertEqual(self.unseen(self.akash), 0)

        self.assertEqual(self.client.post(f"/api/groups/{self.group.id}/seen/", {}, format="json").status_code, 400)

    def test_a_new_member_does_not_inherit_the_backlog(self):
        self.add_expense()
        giri = UserProfile.objects.create(name="Giri", email="g@t.com", username="giri")
        GroupMember.objects.create(group=self.group, user=giri)

        # Nothing that happened before Giri joined counts, even though he never "looked"
        self.assertIsNone(GroupMember.objects.get(group=self.group, user=giri).last_seen_at)
        self.assertEqual(self.unseen(giri), 0)

        self.add_expense(description="After Giri joined", members=[self.akash, giri])
        self.assertEqual(self.unseen(giri), 1)

    def test_someone_outside_the_group_has_nothing_unseen(self):
        stranger = UserProfile.objects.create(name="Stranger", email="s@t.com", username="stranger")
        self.add_expense()
        self.assertEqual(self.unseen(stranger), 0)


class ActivityApiTests(ActivityTestBase):
    def test_group_list_carries_each_persons_unseen_count(self):
        self.add_expense()
        self.add_expense(description="Cab", amount=600)

        for user, expected in ((self.akash, 2), (self.rahul, 0)):
            res = self.client.get(f"/api/groups/?user_id={user.id}")
            self.assertEqual(res.data[0]["unseen_count"], expected)

        # No user_id: no per-person data, and nothing breaks
        self.assertNotIn("unseen_count", self.client.get("/api/groups/").data[0])

    def test_group_detail_carries_the_activity_for_that_person(self):
        expense_id = self.add_expense()
        res = self.client.get(f"/api/groups/{self.group.id}/?user_id={self.akash.id}")

        self.assertIsNotNone(res.data["last_seen_at"])
        self.assertEqual(res.data["unseen_count"], 1)
        entry = res.data["activity"][0]
        self.assertEqual(entry["title"], "Rahul added “Dinner”")
        self.assertEqual(entry["line"], "₹300 · Rahul paid · your share ₹100")
        self.assertEqual(entry["kind"], ActivityEvent.EXPENSE_ADDED)
        self.assertEqual(entry["actor"], "Rahul Kumar")
        self.assertEqual(entry["expense_id"], expense_id)

        # Rahul made it, so it isn't in his feed at all
        mine = self.client.get(f"/api/groups/{self.group.id}/?user_id={self.rahul.id}")
        self.assertEqual(mine.data["activity"], [])

    def test_newest_first_and_capped(self):
        for i in range(3):
            self.add_expense(description=f"Expense {i}")
        feed = self.events_for(self.akash)
        self.assertEqual([e["title"] for e in feed],
                         ["Rahul added “Expense 2”", "Rahul added “Expense 1”", "Rahul added “Expense 0”"])
        self.assertLessEqual(len(activity.for_user(self.group.id, self.akash.id, limit=2)), 2)

    def test_since_filters_to_what_is_new(self):
        self.add_expense(description="Old")
        cutoff = timezone.now()
        self.add_expense(description="New")
        titles = [e.title for e in activity.for_user(self.group.id, self.akash.id, since=cutoff)]
        self.assertEqual(titles, ["Rahul added “New”"])
