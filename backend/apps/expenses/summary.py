"""What a group spent in a month, and what of it was yours.

Everything is derived from the same payer and share rows the balances use, so the
figures here and on the group screen can't drift apart.
"""
from collections import defaultdict
from datetime import date

from .models import Expense, ExpenseCategory, Settlement

CATEGORY_LABELS = dict(ExpenseCategory.choices)


def _month_bounds(month):
    """month is 'YYYY-MM'. Returns (first day, first day of the next month)."""
    year, mon = int(month[:4]), int(month[5:7])
    start = date(year, mon, 1)
    end = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    return start, end


def _previous_month(month):
    year, mon = int(month[:4]), int(month[5:7])
    return f"{year - 1 if mon == 1 else year}-{12 if mon == 1 else mon - 1:02d}"


def _expenses_in(group, month):
    start, end = _month_bounds(month)
    return (Expense.objects.filter(group=group, date__gte=start, date__lt=end)
            .prefetch_related('payers', 'shares')
            .order_by('-amount'))


def _total(expenses):
    return round(sum(float(e.amount) for e in expenses), 2)


def months_with_expenses(group):
    """Newest first, so the month picker only offers months that have something in them."""
    dates = Expense.objects.filter(group=group).dates('date', 'month', order='DESC')
    return [d.strftime('%Y-%m') for d in dates]


def build(group, month, user_id=None):
    expenses = list(_expenses_in(group, month))
    total = _total(expenses)

    per_person = defaultdict(lambda: {"paid": 0.0, "share": 0.0})
    by_category = defaultdict(float)
    your_share = 0.0
    your_paid = 0.0

    for expense in expenses:
        by_category[expense.category] += float(expense.amount)
        for payer in expense.payers.all():
            per_person[payer.user_id]["paid"] += float(payer.amount_paid)
            if payer.user_id == user_id:
                your_paid += float(payer.amount_paid)
        for share in expense.shares.all():
            per_person[share.user_id]["share"] += float(share.amount_owed)
            if share.user_id == user_id:
                your_share += float(share.amount_owed)

    members = {m.id: m for m in group.members.all()}
    people = [
        {
            "user_id": uid,
            "name": members[uid].name if uid in members else f"User #{uid}",
            "paid": round(values["paid"], 2),
            "share": round(values["share"], 2),
        }
        for uid, values in per_person.items()
        if values["paid"] > 0.005 or values["share"] > 0.005
    ]
    people.sort(key=lambda p: p["paid"], reverse=True)

    categories = [
        {"category": key, "label": CATEGORY_LABELS.get(key, key), "total": round(value, 2),
         "percent": round(value * 100 / total, 1) if total else 0.0}
        for key, value in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
    ]

    previous = _previous_month(month)
    previous_total = _total(list(_expenses_in(group, previous)))

    start, end = _month_bounds(month)
    settled = Settlement.objects.filter(group=group, date__gte=start, date__lt=end)

    return {
        "month": month,
        "currency": group.currency or "₹",
        "total": total,
        "expense_count": len(expenses),
        "your_share": round(your_share, 2),
        "your_paid": round(your_paid, 2),
        "previous_month": previous,
        "previous_total": previous_total,
        "change": round(total - previous_total, 2),
        "people": people,
        "categories": categories,
        "biggest": [
            {"id": e.id, "description": e.description, "amount": float(e.amount), "date": e.date}
            for e in expenses[:5]
        ],
        "settled_count": settled.count(),
        "settled_total": round(sum(float(s.amount) for s in settled), 2),
        "available_months": months_with_expenses(group),
    }
