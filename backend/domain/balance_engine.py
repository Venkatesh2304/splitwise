from typing import Dict, List

def calculate_group_balances(
    members: List[int],
    expenses: List[dict],
    settlements: List[dict]
) -> dict:
    """
    Calculates net balance for each member in a group.
    
    :param members: List of user IDs in group.
    :param expenses: List of expense objects/dicts with structure:
           {
               "payers": [{"user_id": int, "amount": float}],
               "shares": [{"user_id": int, "amount": float}]
           }
    :param settlements: List of settlement dicts:
           {
               "payer_id": int,
               "payee_id": int,
               "amount": float
           }
    :return: Dict with:
             - "net_balances": dict[user_id, float]
             - "total_group_spending": float
    """
    balances = {uid: 0.0 for uid in members}
    total_spending = 0.0

    for exp in expenses:
        for p in exp.get("payers", []):
            uid = p["user_id"]
            amt = float(p["amount"])
            if uid in balances:
                balances[uid] += amt
            else:
                balances[uid] = amt
            total_spending += amt

        for s in exp.get("shares", []):
            uid = s["user_id"]
            amt = float(s["amount"])
            if uid in balances:
                balances[uid] -= amt
            else:
                balances[uid] = -amt

    for st in settlements:
        payer_id = st["payer_id"]
        payee_id = st["payee_id"]
        amt = float(st["amount"])

        # Payer paid off debt -> balance increases (+ amt)
        if payer_id in balances:
            balances[payer_id] += amt
        else:
            balances[payer_id] = amt

        # Payee received money -> balance decreases (- amt)
        if payee_id in balances:
            balances[payee_id] -= amt
        else:
            balances[payee_id] = -amt

    # Round net balances to 2 decimal places
    net_balances = {uid: round(bal, 2) for uid, bal in balances.items()}

    return {
        "net_balances": net_balances,
        "total_group_spending": round(total_spending, 2)
    }
