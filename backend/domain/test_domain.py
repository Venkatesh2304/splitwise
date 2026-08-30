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
