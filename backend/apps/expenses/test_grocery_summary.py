import json
from django.test import TestCase
from apps.users.models import UserProfile
from apps.groups.models import Group
from apps.expenses.models import Expense, ExpensePayer, ExpenseShare
from apps.expenses.grocery_summary import build_grocery_summary, match_product_keyword, match_category

class GrocerySummaryTestCase(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="Groceries_Test_Group")
        self.user1 = UserProfile.objects.create(name="Akash Test", username="akash_test_summ", email="akash_test_summ@test.com")
        self.user2 = UserProfile.objects.create(name="Rahul Test", username="rahul_test_summ", email="rahul_test_summ@test.com")
        self.group.members.add(self.user1, self.user2)

        # Expense 1: Itemized split order
        self.exp1 = Expense.objects.create(
            group=self.group,
            description="Blinkit Order #1001",
            amount=1491.0,
            created_by=self.user1,
            notes=json.dumps({
                "platform": "Blinkit",
                "split_mode": "ITEMIZED",
                "items": [
                    {
                        "name": "Meatizon Chicken Breast Boneless 400g",
                        "price": 1000.0,
                        "quantity": 2,
                        "assigned_member_ids": [self.user1.id]
                    },
                    {
                        "name": "Amul Slim n Trim UHT Skimmed Milk",
                        "price": 491.0,
                        "quantity": 5,
                        "assigned_member_ids": [self.user1.id, self.user2.id]
                    }
                ]
            })
        )
        ExpensePayer.objects.create(expense=self.exp1, user=self.user1, amount_paid=1491.0)
        ExpenseShare.objects.create(expense=self.exp1, user=self.user1, amount_owed=1245.5)
        ExpenseShare.objects.create(expense=self.exp1, user=self.user2, amount_owed=245.5)

    def tearDown(self):
        self.exp1.delete()
        self.group.delete()
        self.user1.delete()
        self.user2.delete()

    def test_keyword_matching(self):
        self.assertEqual(match_product_keyword("Fresh Chicken Curry Cut"), "Chicken & Meat")
        self.assertEqual(match_product_keyword("Amul Taaza Milk 1L"), "Milk")
        self.assertEqual(match_product_keyword("Robusta Banana (Kela)"), "Bananas")
        self.assertEqual(match_product_keyword("iD Idli & Dosa Batter"), "Idli & Dosa Batter")
        self.assertEqual(match_product_keyword("Gulab Groundnut Oil 1L"), "Cooking Oil & Ghee")

        self.assertEqual(match_category("Meatizon Chicken Breast"), "Meat, Poultry & Eggs")
        self.assertEqual(match_category("Amul Buttermilk"), "Dairy, Breakfast & Batters")
        self.assertEqual(match_category("Onion Pack of 2"), "Fresh Fruits & Vegetables")

    def test_build_grocery_summary_group_total(self):
        summary = build_grocery_summary(group=self.group)
        self.assertEqual(summary["total_orders"], 1)
        self.assertEqual(summary["total_spend"], 1491.0)
        self.assertEqual(summary["filter_type"], "group_total")
        self.assertTrue(len(summary["categories"]) > 0)
        self.assertTrue(len(summary["products"]) > 0)
        self.assertEqual(len(summary["available_users"]), 2)

    def test_build_grocery_summary_user_split(self):
        # Filter Akash: chicken (1000) + half milk (245.50) = 1245.50
        summary_akash = build_grocery_summary(group=self.group, user_id=self.user1.id)
        self.assertEqual(summary_akash["filter_type"], "user_split")
        self.assertEqual(summary_akash["total_spend"], 1245.5)
        self.assertEqual(summary_akash["active_user"]["name"], self.user1.name)

        chicken_cat = next(c for c in summary_akash["categories"] if c["name"] == "Meat, Poultry & Eggs")
        self.assertEqual(chicken_cat["spend"], 1000.0)

        milk_cat = next(c for c in summary_akash["categories"] if c["name"] == "Dairy, Breakfast & Batters")
        self.assertEqual(milk_cat["spend"], 245.5)

        # Filter Rahul: only half milk (245.50), 0 chicken
        summary_rahul = build_grocery_summary(group=self.group, user_id=self.user2.id)
        self.assertEqual(summary_rahul["filter_type"], "user_split")
        self.assertEqual(summary_rahul["total_spend"], 245.5)
        self.assertEqual(summary_rahul["active_user"]["name"], self.user2.name)

        # Rahul should have Dairy but NOT Meat
        cat_names = [c["name"] for c in summary_rahul["categories"]]
        self.assertIn("Dairy, Breakfast & Batters", cat_names)
        self.assertNotIn("Meat, Poultry & Eggs", cat_names)

    def test_grocery_summary_api_endpoint(self):
        res = self.client.get(f"/api/groups/{self.group.id}/grocery-summary/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_spend"], 1491.0)
        self.assertEqual(data["filter_type"], "group_total")

        # Filter query param
        res_filtered = self.client.get(f"/api/groups/{self.group.id}/grocery-summary/?user_id={self.user1.id}")
        self.assertEqual(res_filtered.status_code, 200)
        data_filtered = res_filtered.json()
        self.assertEqual(data_filtered["filter_type"], "user_split")
        self.assertEqual(data_filtered["total_spend"], 1245.5)

    def test_manual_itemized_split_included_in_summary(self):
        exp_manual = Expense.objects.create(
            group=self.group,
            description="Italian Restaurant Bill",
            amount=500.0,
            split_type="ITEMS",
            created_by=self.user1,
            notes=json.dumps({
                "split_mode": "ITEMIZED",
                "items": [
                    {
                        "name": "Margherita Pizza",
                        "price": 300.0,
                        "split_type": "SPECIFIC",
                        "assigned_member_ids": [self.user1.id]
                    },
                    {
                        "name": "Veg Burger",
                        "price": 200.0,
                        "split_type": "ALL",
                        "assigned_member_ids": [self.user1.id, self.user2.id]
                    }
                ]
            })
        )
        ExpensePayer.objects.create(expense=exp_manual, user=self.user1, amount_paid=500.0)
        ExpenseShare.objects.create(expense=exp_manual, user=self.user1, amount_owed=400.0)
        ExpenseShare.objects.create(expense=exp_manual, user=self.user2, amount_owed=100.0)

        try:
            summary = build_grocery_summary(group=self.group)
            self.assertEqual(summary["total_orders"], 2)
            self.assertEqual(summary["total_spend"], 1991.0)

            summary_akash = build_grocery_summary(group=self.group, user_id=self.user1.id)
            self.assertEqual(summary_akash["total_spend"], 1645.5)

            summary_rahul = build_grocery_summary(group=self.group, user_id=self.user2.id)
            self.assertEqual(summary_rahul["total_spend"], 345.5)

            dining_cat = next(c for c in summary["categories"] if c["name"] == "Dining, Meals & Fast Food")
            self.assertEqual(dining_cat["spend"], 500.0)
        finally:
            exp_manual.delete()

    def test_non_itemized_split_included_in_summary(self):
        exp_wifi = Expense.objects.create(
            group=self.group,
            description="Flat Wi-Fi Bill",
            amount=600.0,
            split_type="EQUAL",
            created_by=self.user1
        )
        ExpensePayer.objects.create(expense=exp_wifi, user=self.user1, amount_paid=600.0)
        ExpenseShare.objects.create(expense=exp_wifi, user=self.user1, amount_owed=300.0)
        ExpenseShare.objects.create(expense=exp_wifi, user=self.user2, amount_owed=300.0)

        try:
            summary = build_grocery_summary(group=self.group)
            self.assertEqual(summary["total_orders"], 2)
            self.assertEqual(summary["itemized_orders"], 1)
            self.assertEqual(summary["non_itemized_orders"], 1)
            self.assertEqual(summary["itemized_spend"], 1491.0)
            self.assertEqual(summary["non_itemized_spend"], 600.0)
            self.assertEqual(summary["total_spend"], 2091.0)

            # Check that "Non-Itemized Spends" exists in categories
            non_item_cat = next(c for c in summary["categories"] if c["name"] == "Non-Itemized Spends")
            self.assertEqual(non_item_cat["spend"], 600.0)

            # Check user filter for Akash: 1245.5 + 300 = 1545.5
            summary_akash = build_grocery_summary(group=self.group, user_id=self.user1.id)
            self.assertEqual(summary_akash["itemized_spend"], 1245.5)
            self.assertEqual(summary_akash["non_itemized_spend"], 300.0)
            self.assertEqual(summary_akash["total_spend"], 1545.5)

            # Check user filter for Rahul: 245.5 + 300 = 545.5
            summary_rahul = build_grocery_summary(group=self.group, user_id=self.user2.id)
            self.assertEqual(summary_rahul["itemized_spend"], 245.5)
            self.assertEqual(summary_rahul["non_itemized_spend"], 300.0)
            self.assertEqual(summary_rahul["total_spend"], 545.5)
        finally:
            exp_wifi.delete()

