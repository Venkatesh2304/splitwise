import json

from rest_framework.test import APITestCase

from apps.expenses.models import Expense, GroceryOrderRecord
from apps.groups.models import Group
from apps.users.models import UserProfile
from apps.users.phone import normalize_phone


def blinkit_order(order_id, total=120.0):
    return {
        "order_id": order_id,
        "placed_at": "1 Nov 2026, 10:00 am",
        "total_amount": total,
        "product_names": ["Milk"],
        "item_details": [{"name": "Milk", "price": total, "quantity": 1}],
        "other_charges": 0.0,
    }


class NormalizePhoneTests(APITestCase):
    def test_shapes_blinkit_and_people_use(self):
        self.assertEqual(normalize_phone("7708024621"), "7708024621")
        self.assertEqual(normalize_phone("+91 77080 24621"), "7708024621")
        self.assertEqual(normalize_phone("917708024621"), "7708024621")
        self.assertEqual(normalize_phone("07708024621"), "7708024621")

    def test_rejects_what_is_not_a_phone(self):
        self.assertIsNone(normalize_phone("http://13.235.142.203:5002"))
        self.assertIsNone(normalize_phone("12345"))
        self.assertIsNone(normalize_phone(""))
        self.assertIsNone(normalize_phone(None))


class BlinkitSyncOwnerTests(APITestCase):
    def setUp(self):
        self.venkatesh = UserProfile.objects.create(username="venkatesh", name="Venkatesh", email="venkatesh@test.com", phone_number="6382247549")
        self.anish = UserProfile.objects.create(username="anish", name="Anish", email="anish@test.com", phone_number="7708024621")

    def sync(self, phone, orders):
        return self.client.post('/api/blinkit/sync_manual/', {"phone_number": phone, "json_data": orders}, format='json')

    def test_sync_goes_to_the_person_with_that_phone(self):
        res = self.sync("+91 77080 24621", [blinkit_order("5001")])
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(GroceryOrderRecord.objects.filter(user=self.anish, order_id="5001").exists())
        self.assertFalse(GroceryOrderRecord.objects.filter(user=self.venkatesh).exists())

    def test_unknown_phone_is_refused_not_saved_under_venkatesh(self):
        res = self.sync("9000000001", [blinkit_order("5002")])
        self.assertEqual(res.status_code, 404)
        self.assertIn("9000000001", str(res.data))
        self.assertFalse(GroceryOrderRecord.objects.exists())

    def test_resync_moves_orders_saved_under_someone_else(self):
        group = Group.objects.create(name="Groceries")
        group.members.add(self.venkatesh, self.anish)
        # What happened before the fix: Anish's order landed under Venkatesh and got split
        GroceryOrderRecord.objects.create(user=self.venkatesh, platform="BLINKIT", order_id="5003", total_amount=120)
        GroceryOrderRecord.objects.create(user=self.venkatesh, platform="BLINKIT", order_id="9999", total_amount=50)
        expense = Expense.objects.create(group=group, description="Blinkit order", amount=120,
                                         notes=json.dumps({"platform": "Blinkit", "order_id": "5003"}))

        res = self.sync("7708024621", [blinkit_order("5003")])
        self.assertEqual(res.status_code, 200, res.data)

        self.assertEqual(GroceryOrderRecord.objects.get(order_id="5003").user, self.anish)
        # Venkatesh's own order stays, and so does the split
        self.assertTrue(GroceryOrderRecord.objects.filter(user=self.venkatesh, order_id="9999").exists())
        self.assertTrue(Expense.objects.filter(id=expense.id).exists())


class PhoneValidationTests(APITestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(username="anish", name="Anish", email="anish@test.com", phone_number="")

    def test_send_otp_refuses_a_url_as_phone(self):
        for path in ('/api/blinkit/send_otp/', '/api/swiggy/send_otp/'):
            res = self.client.post(path, {"user_id": self.user.id, "phone_number": "http://13.235.142.203:5002"}, format='json')
            self.assertEqual(res.status_code, 400, path)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "")

    def test_profile_saves_normalized_phone_and_refuses_junk(self):
        res = self.client.patch(f'/api/users/{self.user.id}/', {"phone_number": "+91 77080 24621"}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "7708024621")

        res = self.client.patch(f'/api/users/{self.user.id}/', {"phone_number": "http://13.235.142.203:5002"}, format='json')
        self.assertEqual(res.status_code, 400)


class OrderForExpenseTests(APITestCase):
    def setUp(self):
        self.akash = UserProfile.objects.create(username="akash", name="Akash", email="akash@test.com")
        self.anish = UserProfile.objects.create(username="anish", name="Anish", email="anish@test.com")
        self.group = Group.objects.create(name="Groceries")
        self.group.members.add(self.akash, self.anish)

    def test_finds_the_order_even_when_someone_else_placed_it(self):
        GroceryOrderRecord.objects.create(user=self.anish, platform="BLINKIT", order_id="7001", total_amount=300,
                                          item_details=[{"name": "Rice", "price": 300, "quantity": 1}])
        # Same id on another platform must not be picked up
        GroceryOrderRecord.objects.create(user=self.akash, platform="INSTAMART", order_id="7001", total_amount=10)
        expense = Expense.objects.create(group=self.group, description="Blinkit", amount=300, notes=json.dumps(
            {"platform": "Blinkit", "order_id": "7001", "split_mode": "ITEMIZED", "items": [{"name": "Rice"}]}))

        res = self.client.get(f'/api/grocery/order_for_expense/{expense.id}/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["order_id"], "7001")
        self.assertEqual(res.data["order_type"], "BLINKIT")
        self.assertEqual(res.data["total_amount"], 300.0)
        self.assertTrue(res.data["is_split"])
        self.assertEqual(res.data["existing_split"]["expense_id"], expense.id)
        self.assertEqual(res.data["existing_split"]["notes_items"], [{"name": "Rice"}])

    def test_plain_expense_is_not_an_order(self):
        expense = Expense.objects.create(group=self.group, description="Dinner", amount=500)
        res = self.client.get(f'/api/grocery/order_for_expense/{expense.id}/')
        self.assertEqual(res.status_code, 404)

    def test_order_no_longer_saved(self):
        expense = Expense.objects.create(group=self.group, description="Blinkit", amount=50,
                                         notes=json.dumps({"platform": "Blinkit", "order_id": "404404"}))
        res = self.client.get(f'/api/grocery/order_for_expense/{expense.id}/')
        self.assertEqual(res.status_code, 404)
