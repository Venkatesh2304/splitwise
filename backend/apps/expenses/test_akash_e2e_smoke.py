import json
from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import UserProfile
from apps.groups.models import Group
from apps.expenses.models import Expense, ExpensePayer, ExpenseShare, GroceryOrderRecord
from apps.expenses.grocery_engine.split_engine import GrocerySplitEngine

class AkashGroceriesE2ESmokeTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test group
        self.group = Group.objects.create(name="Groceries & House")

        # Create members
        self.akash = UserProfile.objects.create(
            name="Akash",
            email="akash@example.com",
            phone_number="6382247549"
        )
        self.venkatesh = UserProfile.objects.create(
            name="Venkatesh",
            email="venkatesh@example.com",
            phone_number="9876543210"
        )
        self.roommate = UserProfile.objects.create(
            name="Roommate",
            email="roommate@example.com",
            phone_number="9123456789"
        )

        self.group.members.add(self.akash, self.venkatesh, self.roommate)

        # Seed sample Blinkit order for Akash
        self.blinkit_order_id = "2612232516"
        GroceryOrderRecord.objects.create(
            user=self.akash,
            platform="BLINKIT",
            order_id=self.blinkit_order_id,
            placed_at="Delivered on 4 Sep, 1:45 PM",
            total_amount=363.0,
            product_names=["Farm Fresh Eggs", "Whole Wheat Bread"],
            item_details=[
                {"name": "Farm Fresh Eggs", "price": 236.0, "quantity": 1},
                {"name": "Whole Wheat Bread", "price": 120.0, "quantity": 1}
            ],
            other_charges=7.0
        )

        # Seed sample Swiggy Instamart order for Akash
        self.swiggy_order_id = "1854321084"
        GroceryOrderRecord.objects.create(
            user=self.akash,
            platform="INSTAMART",
            order_id=self.swiggy_order_id,
            placed_at="Delivered on 4 Sep, 3:10 PM",
            total_amount=826.0,
            product_names=["Amul Milk 1L", "Fortune Refined Oil 1L"],
            item_details=[
                {"name": "Amul Milk 1L", "price": 136.0, "quantity": 2},
                {"name": "Fortune Refined Oil 1L", "price": 655.0, "quantity": 1}
            ],
            other_charges=35.0
        )

    def test_blinkit_orders_api_endpoint(self):
        """Test GET /api/blinkit/orders/?user_id=7 endpoint totals & line items math."""
        response = self.client.get(f"/api/blinkit/orders/?user_id={self.akash.id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        orders = data.get("orders", [])
        self.assertGreaterEqual(len(orders), 1)

        for ord_item in orders:
            tot = float(ord_item["total_amount"])
            other = float(ord_item.get("other_charges", 0.0))
            items = ord_item.get("item_details", [])
            self.assertTrue(len(items) > 0, f"Order {ord_item['order_id']} has empty item_details!")

            sum_items = sum(float(it["price"]) for it in items)
            self.assertAlmostEqual(
                sum_items + other, tot, places=2,
                msg=f"Discrepancy in Blinkit Order #{ord_item['order_id']}: line items sum ({sum_items}) + fees ({other}) != total ({tot})"
            )

    def test_swiggy_orders_api_endpoint(self):
        """Test GET /api/swiggy/orders/?user_id=7 endpoint totals & line items math."""
        response = self.client.get(f"/api/swiggy/orders/?user_id={self.akash.id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        orders = data.get("orders", [])
        self.assertGreaterEqual(len(orders), 1)

        for ord_item in orders:
            tot = float(ord_item["total_amount"])
            other = float(ord_item.get("other_charges", 0.0))
            items = ord_item.get("item_details", [])
            self.assertTrue(len(items) > 0, f"Order {ord_item['order_id']} has empty item_details!")

            sum_items = sum(float(it["price"]) for it in items)
            self.assertAlmostEqual(
                sum_items + other, tot, places=2,
                msg=f"Discrepancy in Swiggy Order #{ord_item['order_id']}: line items sum ({sum_items}) + fees ({other}) != total ({tot})"
            )

    def test_e2e_itemized_split_with_proportional_fees(self):
        """Test POST /api/blinkit/split_order/ with itemized split and ₹7 fee allocation."""
        payload = {
            "group_id": self.group.id,
            "buyer_id": self.akash.id,
            "order_id": self.blinkit_order_id,
            "total_amount": 363.0,
            "split_mode": "ITEMIZED",
            "item_splits": [
                {
                    "name": "Farm Fresh Eggs",
                    "price": 236.0,
                    "split_type": "ALL",
                    "assigned_member_ids": [self.akash.id, self.venkatesh.id, self.roommate.id]
                },
                {
                    "name": "Whole Wheat Bread",
                    "price": 120.0,
                    "split_type": "PERSONAL",
                    "assigned_member_ids": [self.akash.id]
                }
            ]
        }

        res = self.client.post("/api/blinkit/split_order/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 201)
        res_data = res.json()
        owed_breakdown = res_data.get("owed_breakdown", {})

        # Total owed across all members MUST equal total_amount 363.00 EXACTLY
        total_owed = sum(owed_breakdown.values())
        self.assertAlmostEqual(total_owed, 363.0, places=2)

        # Verify DB expense created
        exp = Expense.objects.filter(description__icontains=self.blinkit_order_id).first()
        self.assertIsNotNone(exp)
        self.assertEqual(exp.amount, 363.0)

        # Verify shares created for all 3 members
        shares = ExpenseShare.objects.filter(expense=exp)
        self.assertEqual(shares.count(), 3)
        share_total = sum(s.amount_owed for s in shares)
        self.assertAlmostEqual(share_total, 363.0, places=2)

    def test_e2e_bill_level_custom_split(self):
        """Test POST /api/swiggy/split_order/ with BILL_LEVEL split."""
        payload = {
            "group_id": self.group.id,
            "buyer_id": self.akash.id,
            "order_id": self.swiggy_order_id,
            "total_amount": 826.0,
            "split_mode": "BILL_LEVEL",
            "bill_split": {
                "type": "CUSTOM",
                "custom_amounts": {
                    str(self.akash.id): 426.0,
                    str(self.venkatesh.id): 200.0,
                    str(self.roommate.id): 200.0
                }
            }
        }

        res = self.client.post("/api/swiggy/split_order/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 201)
        res_data = res.json()
        owed = res_data.get("owed_breakdown", {})

        self.assertAlmostEqual(sum(owed.values()), 826.0, places=2)
        self.assertEqual(owed.get(str(self.akash.id)) or owed.get(self.akash.id), 426.0)
        self.assertEqual(owed.get(str(self.venkatesh.id)) or owed.get(self.venkatesh.id), 200.0)

    def test_remove_split_e2e(self):
        """Test removing split for an order."""
        payload = {
            "group_id": self.group.id,
            "buyer_id": self.akash.id,
            "order_id": self.blinkit_order_id,
            "total_amount": 363.0,
            "split_mode": "BILL_LEVEL"
        }
        self.client.post("/api/blinkit/split_order/", data=json.dumps(payload), content_type="application/json")
        self.assertTrue(Expense.objects.filter(description__icontains=self.blinkit_order_id).exists())

        rem_res = self.client.post("/api/blinkit/remove_split/", data=json.dumps({"order_id": self.blinkit_order_id}), content_type="application/json")
        self.assertEqual(rem_res.status_code, 200)
        self.assertFalse(Expense.objects.filter(description__icontains=self.blinkit_order_id).exists())
