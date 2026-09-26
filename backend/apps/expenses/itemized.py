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

import json
import re

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


def extract_expense_items(expense):
    """Unified extractor for itemized line items across all sources:
    - Quick commerce orders (Blinkit, Swiggy Instamart) via notes JSON
    - Manual itemized splits (split_type='ITEMS') via notes JSON
    - GroceryOrderRecord database records (fallback by order #)
    - Description fallback (Item: ₹... | Item2: ₹...)

    Returns: list of dicts with:
      name: str
      price: float
      quantity: int (default 1)
      split_type: str ('ALL', 'PERSONAL', 'SPECIFIC')
      assigned_member_ids: list[int]
      assigned_names: list[str]
    """
    items = []
    if getattr(expense, 'notes', None):
        try:
            nd = json.loads(expense.notes)
            if isinstance(nd, dict):
                items = nd.get('items') or nd.get('products') or []
            elif isinstance(nd, list):
                items = nd
        except Exception:
            pass

    if not items and getattr(expense, 'description', None):
        m = re.search(r'#(\d+)', expense.description)
        if m:
            from apps.expenses.models import GroceryOrderRecord
            rec = GroceryOrderRecord.objects.filter(order_id=m.group(1)).first()
            if rec and rec.item_details and isinstance(rec.item_details, list):
                items = rec.item_details

    if not items and getattr(expense, 'description', None):
        match = re.search(r'\((.*?)\)$', expense.description)
        if match and match.group(1):
            parts = match.group(1).split(' | ')
            for p in parts:
                sub = p.split(': ₹')
                items.append({
                    'name': sub[0].strip() if sub else p,
                    'price': float(sub[1]) if len(sub) > 1 else 0.0,
                    'quantity': 1,
                    'split_type': ALL,
                    'assigned_member_ids': []
                })

    return items or []


def get_expense_source_info(expense):
    """Source identification for any expense: Blinkit, Swiggy, Manual Itemized, or General."""
    notes_dict = {}
    if getattr(expense, 'notes', None):
        try:
            parsed = json.loads(expense.notes)
            if isinstance(parsed, dict):
                notes_dict = parsed
        except Exception:
            pass

    platform = notes_dict.get('platform')
    split_mode = notes_dict.get('split_mode')
    order_id = notes_dict.get('order_id')
    placed_at = notes_dict.get('placed_at')

    if not order_id and getattr(expense, 'description', None):
        m = re.search(r'#(\d+)', expense.description)
        if m:
            order_id = m.group(1)

    is_platform = bool(platform)
    has_items = bool(notes_dict.get('items') or notes_dict.get('products'))
    is_itemized = (
        getattr(expense, 'split_type', None) == 'ITEMS'
        or split_mode == 'ITEMIZED'
        or is_platform
        or has_items
    )

    if platform:
        source_type = 'BLINKIT' if 'blinkit' in platform.lower() else 'SWIGGY'
        source_label = platform
    elif is_itemized:
        source_type = 'MANUAL'
        source_label = 'Itemized Bill'
    else:
        source_type = 'GENERAL'
        source_label = 'Expense'

    return {
        'source_type': source_type,
        'source_label': source_label,
        'is_platform': is_platform,
        'is_itemized': is_itemized,
        'platform': platform,
        'order_id': order_id,
        'placed_at': placed_at,
    }
