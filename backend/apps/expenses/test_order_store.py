from django.test import TestCase
from apps.users.models import UserProfile
from apps.expenses.models import GroceryOrderRecord
from apps.expenses.grocery_engine.order_store import OrderStoreManager
from apps.expenses.swiggy_views import parse_swiggy_orders_json

class OrderStoreManagerTestCase(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(
            name="Test User",
            email="testuser@example.com",
            phone_number="9999999999"
        )

    def test_swiggy_mcp_parser(self):
        mcp_payload = {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": '{"orders": [{"orderId": "ORD123", "totalAmount": 450, "currentStatus": "Delivered on 4 Sep", "items": [{"name": "Milk", "quantity": 2}], "billDetails": {"itemTotal": 400, "grandTotal": 450}}]}'
                    }
                ]
            }
        }
        orders = parse_swiggy_orders_json(mcp_payload)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["order_id"], "ORD123")
        self.assertEqual(orders[0]["total_amount"], 450.0)

    def test_order_immutability_and_non_deletion(self):
        initial_orders = [
            {
                "order_id": "ORD001",
                "placed_at": "1 Sep",
                "total_amount": 200.0,
                "product_names": ["Bread"],
                "item_details": [{"name": "Bread", "price": 200.0, "quantity": 1}],
                "other_charges": 0.0
            },
            {
                "order_id": "ORD002",
                "placed_at": "2 Sep",
                "total_amount": 300.0,
                "product_names": ["Butter"],
                "item_details": [{"name": "Butter", "price": 300.0, "quantity": 1}],
                "other_charges": 0.0
            }
        ]

        # 1. First save
        merged1 = OrderStoreManager.save_and_merge_orders(self.user, "INSTAMART", initial_orders)
        self.assertEqual(len(merged1), 2)
        self.assertEqual(GroceryOrderRecord.objects.filter(user=self.user).count(), 2)

        # 2. Second fetch with missing ORD001 and edited details for ORD002 + new ORD003
        fresh_orders = [
            {
                "order_id": "ORD002",
                "placed_at": "MODIFIED DATE",
                "total_amount": 9999.0, # Attempts to modify ORD002
                "product_names": ["MODIFIED PRODUCT"],
                "item_details": [],
                "other_charges": 0.0
            },
            {
                "order_id": "ORD003",
                "placed_at": "3 Sep",
                "total_amount": 150.0,
                "product_names": ["Jam"],
                "item_details": [{"name": "Jam", "price": 150.0, "quantity": 1}],
                "other_charges": 0.0
            }
        ]

        merged2 = OrderStoreManager.save_and_merge_orders(self.user, "INSTAMART", fresh_orders)

        # Assert total records count is 3 (ORD001 retained, ORD002 kept, ORD003 added)
        self.assertEqual(len(merged2), 3)
        self.assertEqual(GroceryOrderRecord.objects.filter(user=self.user).count(), 3)

        # Assert ORD002 was NOT mutated
        ord002_record = GroceryOrderRecord.objects.get(user=self.user, order_id="ORD002")
        self.assertEqual(ord002_record.total_amount, 300.0)
        self.assertEqual(ord002_record.product_names, ["Butter"])
