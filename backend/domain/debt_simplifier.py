import heapq

def simplify_debts(net_balances: dict[int, float]) -> list[dict]:
    """
    Minimizes the number of transactions needed to settle all debts.
    
    :param net_balances: Dictionary mapping user_id to their net balance (rounded to 2 decimals).
                         Positive balance means user is owed money (creditor).
                         Negative balance means user owes money (debtor).
    :return: List of simplified settlement transactions:
             [{"from_user_id": debtor_id, "to_user_id": creditor_id, "amount": amount}]
    """
    # Filter out users with zero or negligible balance
    debtors = []   # Store (-balance, user_id) for max-heap behavior with heapq
    creditors = [] # Store (-balance, user_id) where balance > 0 => (-balance < 0)

    for user_id, bal in net_balances.items():
        bal = round(bal, 2)
        if bal < -0.009:
            # User owes money: bal is negative
            heapq.heappush(debtors, (bal, user_id)) # Most negative balance comes first
        elif bal > 0.009:
            # User is owed money: bal is positive
            heapq.heappush(creditors, (-bal, user_id)) # Largest positive balance comes first

    transactions = []

    while debtors and creditors:
        debt_val, debtor_id = heapq.heappop(debtors)
        cred_val, creditor_id = heapq.heappop(creditors)

        debt_amount = -debt_val  # positive float owed by debtor
        cred_amount = -cred_val  # positive float owed to creditor

        settle_amount = round(min(debt_amount, cred_amount), 2)

        if settle_amount > 0:
            transactions.append({
                "from_user_id": debtor_id,
                "to_user_id": creditor_id,
                "amount": settle_amount
            })

        remaining_debt = round(debt_amount - settle_amount, 2)
        remaining_cred = round(cred_amount - settle_amount, 2)

        if remaining_debt > 0.009:
            heapq.heappush(debtors, (-remaining_debt, debtor_id))
        if remaining_cred > 0.009:
            heapq.heappush(creditors, (-remaining_cred, creditor_id))

    return transactions
