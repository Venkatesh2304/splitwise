"""Working out who owes what when a bill is split item by item.

Each item is charged to the people it was assigned to; whatever the items don't
account for (tax, delivery, service charge) is spread in proportion to what each
person's items came to, so someone with one ₹20 item doesn't carry the same tax as
someone with ₹800 of shopping. Any rounding difference goes to whoever paid, so the
shares always add up to the bill exactly.

This is the single implementation: both a Blinkit/Swiggy order split
(`grocery_engine.split_engine`) and a hand-entered itemised expense
(`ExpenseSerializer`) come through here, so they can't drift apart.
"""

# How an item names the people it's charged to
ALL = 'ALL'              # everyone in the group
PERSONAL = 'PERSONAL'    # one person (the first assigned, else whoever paid)
SPECIFIC = 'SPECIFIC'    # exactly the people listed


def assigned_ids(item, member_ids, personal_fallback):
    """The people an item is charged to, after its mode is taken into account."""
    mode = item.get('split_type') or SPECIFIC
    listed = [uid for uid in (item.get('assigned_member_ids') or []) if uid in member_ids]

    if mode == ALL:
        return list(member_ids)
    if mode == PERSONAL:
        return [listed[0]] if listed else [personal_fallback]
    return listed or list(member_ids)


def split_items(total_amount, items, member_ids, remainder_to):
    """{user_id: amount owed} for every member, summing exactly to total_amount.

    items: [{name, price, split_type, assigned_member_ids}] — the shape stored in an
    expense's notes JSON.
    """
    owed = {uid: 0.0 for uid in member_ids}
    subtotals = {uid: 0.0 for uid in member_ids}

    for item in items:
        price = float(item.get('price') or 0.0)
        targets = assigned_ids(item, member_ids, remainder_to)
        if not targets:
            continue
        share = price / len(targets)
        for uid in targets:
            if uid in subtotals:
                subtotals[uid] += share

    items_total = sum(float(item.get('price') or 0.0) for item in items)
    charges = max(0.0, round(total_amount - items_total, 2))
    subtotal_sum = sum(subtotals.values()) or 1.0

    for uid in member_ids:
        fee_share = (subtotals[uid] / subtotal_sum) * charges if charges > 0 else 0.0
        owed[uid] = round(subtotals[uid] + fee_share, 2)

    # Whoever paid absorbs the rounding, so the shares add up to the bill
    difference = round(total_amount - sum(owed.values()), 2)
    if difference != 0 and remainder_to in owed:
        owed[remainder_to] = round(owed[remainder_to] + difference, 2)

    return owed
