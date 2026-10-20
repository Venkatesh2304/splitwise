from unittest.mock import patch

from rest_framework.test import APITestCase
from django.test import TestCase

from apps.users.models import UserProfile
from apps.expenses.models import GroceryOrderRecord
from apps.expenses.swiggy_views import (
    parse_swiggy_food_orders,
    rescale_item_lines,
    mcp_text_payloads,
    FOOD_PLATFORM,
    INSTAMART_PLATFORM,
)


def food_list(order_id="9001", total=520.0, restaurant="Idli Corner", active=False):
    return {
        "success": True,
        "data": {
            "orders": [{
                "orderId": order_id,
                "restaurantName": restaurant,
                "orderTotal": total,
                "orderStatus": "Delivered",
                "orderedTime": "2026-10-12T19:30:00Z",
                "isActiveOrder": active,
            }]
        },
    }


def food_detail(order_id="9001", items=None, **bill):
    order = {
        "order_id": order_id,
        "order_time": "2026-10-12T19:30:00Z",
        "restaurant_name": "Idli Corner",
        "item_total": bill.get("item_total", 450.0),
        "order_tax": bill.get("order_tax", 22.5),
        "order_delivery_charge": bill.get("order_delivery_charge", 47.5),
        "order_discount": bill.get("order_discount", 0.0),
        "coupon_discount": bill.get("coupon_discount", 0.0),
        "order_total": bill.get("order_total", 520.0),
        "order_items": items if items is not None else [
            {"name": "Ghee Podi Idli", "quantity": 2, "total": 300.0, "base_price": 150.0, "packing_charges": 0.0},
            {"name": "Filter Coffee", "quantity": 1, "total": 150.0, "base_price": 150.0, "packing_charges": 0.0},
        ],
    }
    return {"success": True, "data": {"order": order}}


class SwiggyFoodParserTests(TestCase):
    """The parser is pure, so none of this needs the network."""

    def assert_invariant(self, order):
        """What the split UI and test_akash_e2e_smoke both rely on."""
        line_sum = sum(float(i["price"]) for i in order["item_details"])
        self.assertAlmostEqual(
            line_sum + float(order["other_charges"]), float(order["total_amount"]), places=2,
            msg=f"items {line_sum} + fees {order['other_charges']} != total {order['total_amount']}")
        self.assertGreaterEqual(order["other_charges"], 0.0)

    def test_parses_order_and_holds_invariant(self):
        orders = parse_swiggy_food_orders(food_list(), {"9001": food_detail()})
        self.assertEqual(len(orders), 1)
        o = orders[0]
        self.assertEqual(o["order_id"], "9001")
        self.assertEqual(o["order_type"], FOOD_PLATFORM)
        self.assertEqual(o["restaurant_name"], "Idli Corner")
        self.assertEqual(len(o["item_details"]), 2)
        self.assertEqual(o["total_amount"], 520.0)
        self.assert_invariant(o)

    def test_coupon_discount_never_makes_charges_negative(self):
        # Items are worth more than was actually paid once a coupon lands.
        detail = food_detail(order_total=300.0, coupon_discount=220.0)
        orders = parse_swiggy_food_orders(food_list(total=300.0), {"9001": detail})
        o = orders[0]
        self.assert_invariant(o)
        self.assertGreaterEqual(o["other_charges"], 0.0)
        # The pricier dish still carries the larger share.
        self.assertGreater(o["item_details"][0]["price"], o["item_details"][1]["price"])

    def test_variants_and_addons_raise_the_line(self):
        plain = [
            {"name": "Dosa", "quantity": 1, "base_price": 100.0},
            {"name": "Dosa", "quantity": 1, "base_price": 100.0},
        ]
        with_extras = [
            {"name": "Dosa", "quantity": 1, "base_price": 100.0,
             "variants": [{"name": "Large", "price": 40.0}],
             "addons": [{"name": "Extra chutney", "price": 20.0}]},
            {"name": "Dosa", "quantity": 1, "base_price": 100.0},
        ]
        flat = parse_swiggy_food_orders(food_list(), {"9001": food_detail(items=plain)})[0]
        fancy = parse_swiggy_food_orders(food_list(), {"9001": food_detail(items=with_extras)})[0]
        self.assertAlmostEqual(flat["item_details"][0]["price"], flat["item_details"][1]["price"], places=2)
        self.assertGreater(fancy["item_details"][0]["price"], fancy["item_details"][1]["price"])
        self.assertIn("Large", fancy["item_details"][0]["name"])
        self.assert_invariant(fancy)

    def test_active_order_is_skipped(self):
        # Still being delivered: no final bill, and the total can still move.
        self.assertEqual(parse_swiggy_food_orders(food_list(active=True), {}), [])

    def test_order_without_details_still_splittable(self):
        orders = parse_swiggy_food_orders(food_list(), {})
        o = orders[0]
        self.assertEqual(len(o["item_details"]), 1)
        self.assert_invariant(o)

    def test_rescale_hits_the_target_exactly(self):
        lines = rescale_item_lines([100.0, 33.33, 66.67], 150.0)
        self.assertAlmostEqual(sum(lines), 150.0, places=2)
        lines = rescale_item_lines([0.0, 0.0], 50.0)
        self.assertAlmostEqual(sum(lines), 50.0, places=2)
        self.assertEqual(rescale_item_lines([], 10.0), [])

    def test_mcp_envelope_unwraps_text_blocks(self):
        envelope = {"result": {"content": [
            {"type": "text", "text": '{"orders": [{"orderId": "1"}]}'},
            {"type": "image", "data": "ignored"},
        ]}}
        payloads = mcp_text_payloads(envelope)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["orders"][0]["orderId"], "1")
        self.assertEqual(mcp_text_payloads({}), [])


class SwiggyMergedListTests(APITestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(name="Alex", username="alex", phone_number="9000000001", email="alex1@example.test")
        GroceryOrderRecord.objects.create(
            user=self.user, platform=INSTAMART_PLATFORM, order_id="5550001",
            placed_at="10 Oct 2026, 06:00 PM", total_amount=200.0, other_charges=0.0,
            product_names=["Milk"], item_details=[{"name": "Milk", "price": 200.0, "quantity": 1}],
            raw_payload={}, full_order_json={"orderTime": "2026-10-10T18:00:00Z"})
        GroceryOrderRecord.objects.create(
            user=self.user, platform=FOOD_PLATFORM, order_id="9001",
            placed_at="12 Oct 2026, 07:30 PM", total_amount=520.0, other_charges=70.0,
            product_names=["Ghee Podi Idli"],
            item_details=[{"name": "Ghee Podi Idli", "price": 450.0, "quantity": 2}],
            raw_payload={}, full_order_json={"orderTime": "2026-10-12T19:30:00Z", "restaurant_name": "Idli Corner"})

    def test_orders_endpoint_merges_both_platforms_newest_first(self):
        res = self.client.get(f"/api/swiggy/orders/?user_id={self.user.id}")
        self.assertEqual(res.status_code, 200)
        orders = res.json()["orders"]
        self.assertEqual(len(orders), 2)
        self.assertEqual([o["order_id"] for o in orders], ["9001", "5550001"])
        self.assertEqual({o["order_type"] for o in orders}, {FOOD_PLATFORM, INSTAMART_PLATFORM})

    def test_expired_session_reports_reconnect_and_keeps_saved_orders(self):
        self.user.swiggy_access_token = "dead-token"
        self.user.swiggy_refresh_token = "dead-refresh"
        self.user.save()

        class R:
            status_code = 401
            text = '{"error":"invalid_token"}'
            headers = {}

            def json(self):
                return {"error": "invalid_token"}

        with patch("apps.expenses.swiggy_views.requests.post", return_value=R()):
            res = self.client.get(f"/api/swiggy/orders/?refresh=true&user_id={self.user.id}")

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["needs_reconnect"])
        # Stale beats blank: the saved orders are still listed.
        self.assertEqual(len(body["orders"]), 2)


class OrderNamespaceScopingTests(APITestCase):
    """A food order id can be a prefix of an Instamart one. Splitting or un-splitting
    one must not delete the other's expense — process_split deletes what it matches."""

    def setUp(self):
        from apps.groups.models import Group
        self.user = UserProfile.objects.create(name="Alex", username="alex", phone_number="9000000002", email="alex@example.test")
        self.other = UserProfile.objects.create(name="Sam", username="sam", phone_number="9000000003", email="sam@example.test")
        self.group = Group.objects.create(name="Groceries", category="HOME", currency="₹")
        self.group.members.add(self.user, self.other)

    def _split(self, endpoint, order_id, amount):
        return self.client.post(f"/api/{endpoint}/split_order/", {
            "group_id": self.group.id,
            "buyer_id": self.user.id,
            "actor_id": self.user.id,
            "order_id": order_id,
            "platform": "SWIGGY_FOOD" if endpoint == "swiggy" else "BLINKIT",
            "total_amount": amount,
            "split_mode": "BILL_LEVEL",
            "bill_split": {"mode": "ALL"},
            "description": f"Order #{order_id}",
        }, format="json")

    def test_prefix_order_ids_do_not_clobber_each_other(self):
        from apps.expenses.models import Expense
        self.assertEqual(self._split("swiggy", "12345", 300.0).status_code, 201)
        self.assertEqual(self._split("swiggy", "123456", 400.0).status_code, 201)
        # Both survive: the shorter id used to match the longer one's expense.
        self.assertEqual(Expense.objects.count(), 2)

        res = self.client.post("/api/swiggy/remove_split/", {
            "order_id": "12345", "actor_id": self.user.id, "platform": "SWIGGY_FOOD",
        }, format="json")
        self.assertEqual(res.status_code, 200)
        remaining = list(Expense.objects.all())
        self.assertEqual(len(remaining), 1)
        self.assertIn("123456", remaining[0].description)
