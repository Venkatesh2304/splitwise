from django.test import TestCase
from domain.debt_simplifier import simplify_debts
from domain.split_calculator import calculate_splits, SplitType
from domain.balance_engine import calculate_group_balances

class DomainEngineTests(TestCase):
    def test_debt_simplification_basic(self):
        # Alice (1) is owed 50, Bob (2) owes 30, Charlie (3) owes 20
        balances = {1: 50.0, 2: -30.0, 3: -20.0}
        txs = simplify_debts(balances)
        self.assertEqual(len(txs), 2)
        
        total_settled = sum(t['amount'] for t in txs)
        self.assertEqual(total_settled, 50.0)

    def test_debt_simplification_transitive(self):
        # Alice (1) owed 40, Bob (2) owes 0 (net), Charlie (3) owes 40
        # Instead of 3 -> 2 ($40) and 2 -> 1 ($40), direct transaction: 3 -> 1 ($40)
        balances = {1: 40.0, 2: 0.0, 3: -40.0}
        txs = simplify_debts(balances)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]['from_user_id'], 3)
        self.assertEqual(txs[0]['to_user_id'], 1)
        self.assertEqual(txs[0]['amount'], 40.0)

    def test_split_calculator_equal(self):
        owed, err = calculate_splits(100.0, SplitType.EQUAL, [1, 2, 3])
        self.assertIsNone(err)
        self.assertEqual(sum(owed.values()), 100.0)
        self.assertEqual(owed[1], 33.34) # Rounding diff adjusted on user 1
        self.assertEqual(owed[2], 33.33)
        self.assertEqual(owed[3], 33.33)

    def test_split_calculator_percentage(self):
        owed, err = calculate_splits(200.0, SplitType.PERCENTAGE, [1, 2], {1: 60.0, 2: 40.0})
        self.assertIsNone(err)
        self.assertEqual(owed[1], 120.0)
        self.assertEqual(owed[2], 80.0)

    def test_split_calculator_shares(self):
        # A ₹600 rent split 2:1 — two people in the big room, one in the small
        owed, err = calculate_splits(600.0, SplitType.SHARES, [1, 2], {1: 2, 2: 1})
        self.assertIsNone(err)
        self.assertEqual(owed[1], 400.0)
        self.assertEqual(owed[2], 200.0)

    def test_split_calculator_shares_add_up_to_the_paisa(self):
        """What the whole thing is for: no amount of odd ratios may lose or invent money."""
        for total, units in [
            (100.0, {1: 1, 2: 1, 3: 1}),          # thirds
            (100.0, {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}),   # sevenths
            (1234.57, {1: 3, 2: 2, 3: 1}),
            (0.03, {1: 1, 2: 1, 3: 1, 4: 1}),     # less than a paisa each
        ]:
            with self.subTest(total=total, units=units):
                owed, err = calculate_splits(total, SplitType.SHARES, list(units), units)
                self.assertIsNone(err)
                self.assertEqual(round(sum(owed.values()), 2), total)
                # Nobody carries the whole rounding difference: one paisa at most each
                for uid, share in owed.items():
                    exact = total * units[uid] / sum(units.values())
                    self.assertLessEqual(abs(share - exact), 0.01)

    def test_split_calculator_shares_can_leave_someone_out(self):
        """Zero shares means this one wasn't theirs, which is allowed — all zero isn't."""
        owed, err = calculate_splits(90.0, SplitType.SHARES, [1, 2, 3], {1: 1, 2: 2, 3: 0})
        self.assertIsNone(err)
        self.assertEqual(owed, {1: 30.0, 2: 60.0, 3: 0.0})

        owed, err = calculate_splits(90.0, SplitType.SHARES, [1, 2], {1: 0, 2: 0})
        self.assertEqual(owed, {})
        self.assertIn("at least one person", err)

    def test_split_calculator_shares_refuses_a_negative_share(self):
        owed, err = calculate_splits(90.0, SplitType.SHARES, [1, 2], {1: 3, 2: -1})
        self.assertEqual(owed, {})
        self.assertIn("less than zero", err)

    def test_balance_engine(self):
        members = [1, 2, 3]
        expenses = [{
            "payers": [{"user_id": 1, "amount": 120.0}],
            "shares": [{"user_id": 1, "amount": 40.0}, {"user_id": 2, "amount": 40.0}, {"user_id": 3, "amount": 40.0}]
        }]
        settlements = [{
            "payer_id": 2,
            "payee_id": 1,
            "amount": 40.0
        }]
        res = calculate_group_balances(members, expenses, settlements)
        self.assertEqual(res['net_balances'][1], 40.0)  # +120 -40 -40 = +40
        self.assertEqual(res['net_balances'][2], 0.0)   # 0 -40 +40 = 0
        self.assertEqual(res['net_balances'][3], -40.0) # 0 -40 = -40
