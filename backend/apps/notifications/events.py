"""Turns expense/settlement changes into personalised notifications.

Who hears about a change: everyone *involved* (paid something or has a share above zero;
for an edit, involved before or after) except the person who made the change. Each
recipient gets text written from their own point of view ("you owe", "you get back").

Every change is snapshotted before it happens, because an edit or delete destroys the
payer/share rows the message needs.
"""
import json
import re
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from apps.users.models import UserProfile

from . import push
from .models import ActivityEvent

EPSILON = 0.005
DEFAULT_SETTLEMENT_NOTE = "Payment settlement via Splitwise"

# ---------------------------------------------------------------- helpers

def resolve_actor(actor_id):
    """The user who made the change, from the client's actor_id. None if missing/unknown."""
    if actor_id in (None, ""):
        return None
    try:
        return UserProfile.objects.filter(id=int(actor_id)).first()
    except (TypeError, ValueError):
        return None

def first_name(user):
    return (user.name or user.username or "Someone").split(" ")[0] if user else "Someone"

def money(value, currency="₹"):
    q = Decimal(str(abs(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole = int(q)
    paise = int((q - whole) * 100)
    if currency == "₹":
        digits = str(whole)
        if len(digits) > 3:
            head, tail = digits[:-3], digits[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            digits = ",".join(groups + [tail])
    else:
        digits = f"{whole:,}"
    return f"{'-' if value < 0 else ''}{currency}{digits}" + (f".{paise:02d}" if paise else "")

def _notes_json(notes):
    try:
        parsed = json.loads(notes or "")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}

def clean_title(description):
    # Mirrors getCleanTitle() in GroupDetailView.jsx: drop a trailing "(...)" product list
    return re.sub(r"\s*\([^)]*\)$", "", description or "").strip() or "an expense"

def _quote(text):
    return f"“{text}”"

# ---------------------------------------------------------------- snapshots

def snapshot_expense(expense):
    people = {}
    payer_ids = []
    for p in expense.payers.all():
        entry = people.setdefault(p.user_id, {"paid": 0.0, "owed": 0.0})
        entry["paid"] += float(p.amount_paid)
        if float(p.amount_paid) > EPSILON:
            payer_ids.append(p.user_id)
    for s in expense.shares.all():
        people.setdefault(s.user_id, {"paid": 0.0, "owed": 0.0})["owed"] += float(s.amount_owed)
    names = {u.id: first_name(u) for u in UserProfile.objects.filter(id__in=list(people))}
    notes = _notes_json(expense.notes)
    return {
        "id": expense.id,
        "group_id": expense.group_id,
        "group_name": expense.group.name,
        "currency": expense.group.currency or "₹",
        "description": clean_title(expense.description),
        "amount": float(expense.amount),
        "platform": notes.get("platform"),
        "order_id": notes.get("order_id"),
        "people": people,
        "names": names,
        "payer_ids": payer_ids,
    }

def snapshot_settlement(settlement):
    return {
        "id": settlement.id,
        "group_id": settlement.group_id,
        "group_name": settlement.group.name,
        "currency": settlement.group.currency or "₹",
        "amount": float(settlement.amount),
        "notes": (settlement.notes or "").strip(),
        "payer_id": settlement.payer_id,
        "payee_id": settlement.payee_id,
        "names": {settlement.payer_id: first_name(settlement.payer), settlement.payee_id: first_name(settlement.payee)},
    }

def involved(snapshot):
    return {
        uid for uid, v in snapshot["people"].items()
        if v["paid"] > EPSILON or v["owed"] > EPSILON
    }

def _recipients(user_ids, actor):
    actor_id = actor.id if actor else None
    return sorted(uid for uid in user_ids if uid != actor_id)

def _person(snapshot, uid):
    return snapshot["people"].get(uid, {"paid": 0.0, "owed": 0.0})

def _tag(snapshot, tag=None):
    if tag:
        return tag
    if snapshot.get("order_id"):
        return f"order-{snapshot['order_id']}"
    return f"expense-{snapshot['id']}"

def _payer_phrase(snapshot, uid):
    payers = snapshot["payer_ids"]
    if not payers:
        return None
    if payers == [uid]:
        return "you paid"
    # Put the reader first when they're one of the payers, so they aren't told
    # "Akash & 1 other paid" about a bill they helped pay
    if uid in payers:
        others = len(payers) - 1
        return f"you & {others} other{'s' if others > 1 else ''} paid"
    first = snapshot["names"].get(payers[0], "Someone")
    if len(payers) == 1:
        return f"{first} paid"
    return f"{first} & {len(payers) - 1} other{'s' if len(payers) > 2 else ''} paid"

def _position(snapshot, uid, past=False):
    """What this expense means for one person: 'you get back ₹574' / 'your share ₹200'."""
    cur = snapshot["currency"]
    p = _person(snapshot, uid)
    net = p["paid"] - p["owed"]
    if p["paid"] > EPSILON and net > EPSILON:
        return f"you {'were getting' if past else 'get'} back {money(net, cur)}"
    if p["owed"] > EPSILON:
        return f"your share {'was ' if past else ''}{money(p['owed'], cur)}"
    return None

def _join(*parts):
    return " · ".join(p for p in parts if p)

def _expense_url(snapshot, expense_id=None):
    url = f"/?group={snapshot['group_id']}"
    return url + (f"&expense={expense_id}" if expense_id else "")

def _is_generated_title(snapshot):
    platform = snapshot.get("platform") or ""
    return bool(platform) and bool(re.match(rf"^{re.escape(platform)} order #", snapshot["description"], re.I))

def _emit(kind, group_id, actor, title, url, messages, expense_id=None):
    """Record the change, then notify. Both read from the same per-person lines, so the
    app and the notification can never word the same change differently."""
    if messages:
        ActivityEvent.objects.create(
            group_id=group_id,
            actor=actor,
            kind=kind,
            expense_id=expense_id,
            title=title,
            url=url,
            lines={str(uid): payload["body"] for uid, payload in messages},
        )
    push.queue(messages)
    return messages

# ---------------------------------------------------------------- events

def expense_added(expense, actor, tag=None):
    snap = snapshot_expense(expense)
    who = first_name(actor)
    if snap["platform"]:
        what = f"a {snap['platform']} order" if _is_generated_title(snap) else _quote(snap["description"])
        title = f"🛒 {who} split {what}"
    else:
        title = f"{who} added {_quote(snap['description'])}"

    messages = []
    for uid in _recipients(involved(snap), actor):
        body = _join(money(snap["amount"], snap["currency"]), _payer_phrase(snap, uid), _position(snap, uid))
        messages.append((uid, {
            "title": title, "body": body, "tag": _tag(snap, tag),
            "url": _expense_url(snap, snap["id"]), "group_id": snap["group_id"],
        }))
    return _emit(ActivityEvent.EXPENSE_ADDED, snap["group_id"], actor, title,
                 _expense_url(snap, snap["id"]), messages, expense_id=snap["id"])

def expense_edited(before, expense, actor, tag=None):
    after = snapshot_expense(expense)
    cur = after["currency"]
    title = f"{'🛒 ' if after['platform'] else ''}{first_name(actor)} updated {_quote(after['description'])}"

    if abs(before["amount"] - after["amount"]) > EPSILON:
        total = f"total {money(before['amount'], cur)} → {money(after['amount'], cur)}"
    else:
        total = f"total {money(after['amount'], cur)}"

    messages = []
    for uid in _recipients(involved(before) | involved(after), actor):
        old_share = _person(before, uid)["owed"]
        new_share = _person(after, uid)["owed"]
        if abs(old_share - new_share) > EPSILON:
            share = f"your share {money(old_share, cur)} → {money(new_share, cur)}"
        else:
            share = f"your share unchanged ({money(new_share, cur)})"
        messages.append((uid, {
            "title": title, "body": _join(share, total), "tag": _tag(after, tag),
            "url": _expense_url(after, after["id"]), "group_id": after["group_id"],
        }))
    return _emit(ActivityEvent.EXPENSE_EDITED, after["group_id"], actor, title,
                 _expense_url(after, after["id"]), messages, expense_id=after["id"])

def expense_deleted(before, actor, tag=None):
    title = f"{first_name(actor)} deleted {_quote(before['description'])}"
    messages = []
    for uid in _recipients(involved(before), actor):
        body = _join(money(before["amount"], before["currency"]), _position(before, uid, past=True))
        messages.append((uid, {
            "title": title, "body": body, "tag": _tag(before, tag),
            "url": _expense_url(before), "group_id": before["group_id"],
        }))
    return _emit(ActivityEvent.EXPENSE_DELETED, before["group_id"], actor, title,
                 _expense_url(before), messages)

NUDGE_COOLDOWN = timedelta(hours=6)

def nudge_cooldown_remaining(group, actor, debtor):
    """How long before this person may be nudged again, or None if they can be now."""
    last = ActivityEvent.objects.filter(
        group=group, actor=actor, kind=ActivityEvent.NUDGED, lines__has_key=str(debtor.id)
    ).first()
    if last is None:
        return None
    left = (last.created_at + NUDGE_COOLDOWN) - timezone.now()
    if left <= timedelta(0):
        return None
    hours, minutes = divmod(int(left.total_seconds()) // 60, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"

def nudged(group, actor, debtor, amount):
    currency = group.currency or "₹"
    title = f"👋 {first_name(actor)} is asking you to settle up"
    body = _join(
        f"you owe {money(amount, currency)}" if amount > EPSILON else None,
        group.name,
    )
    messages = [(debtor.id, {
        "title": title, "body": body, "tag": f"nudge-{group.id}-{actor.id}",
        "url": f"/?group={group.id}", "group_id": group.id,
    })]
    return _emit(ActivityEvent.NUDGED, group.id, actor, f"{first_name(actor)} nudged {first_name(debtor)}",
                 f"/?group={group.id}", messages)

def _settlement_party(snap, uid, subject, as_subject):
    if subject == uid:
        return "You" if as_subject else "you"
    return snap["names"].get(subject, "Someone")

def settlement_recorded(settlement, actor):
    snap = snapshot_settlement(settlement)
    amount = money(snap["amount"], snap["currency"])
    third_party = actor is not None and actor.id not in (snap["payer_id"], snap["payee_id"])
    note = snap["notes"] if snap["notes"] and snap["notes"] != DEFAULT_SETTLEMENT_NOTE else None

    messages = []
    for uid in _recipients({snap["payer_id"], snap["payee_id"]}, actor):
        payer = _settlement_party(snap, uid, snap["payer_id"], as_subject=True)
        payee = _settlement_party(snap, uid, snap["payee_id"], as_subject=False)
        body = _join(note, f"recorded by {first_name(actor)}" if third_party else None, snap["group_name"])
        messages.append((uid, {
            "title": f"💸 {payer} paid {payee} {amount}", "body": body,
            "tag": f"settlement-{snap['id']}", "url": f"/?group={snap['group_id']}", "group_id": snap["group_id"],
        }))
    # The title is written from each reader's side ("You paid…"), so the stored one names
    # both people instead
    shared_title = f"💸 {snap['names'].get(snap['payer_id'], 'Someone')} paid {snap['names'].get(snap['payee_id'], 'someone')} {amount}"
    return _emit(ActivityEvent.SETTLEMENT_RECORDED, snap["group_id"], actor, shared_title,
                 f"/?group={snap['group_id']}", messages)

def settlement_deleted(snap, actor):
    amount = money(snap["amount"], snap["currency"])
    messages = []
    for uid in _recipients({snap["payer_id"], snap["payee_id"]}, actor):
        payer = _settlement_party(snap, uid, snap["payer_id"], as_subject=True)
        payee = _settlement_party(snap, uid, snap["payee_id"], as_subject=False)
        messages.append((uid, {
            "title": f"{first_name(actor)} deleted a settle-up",
            "body": _join(f"{payer} paid {payee} {amount}", snap["group_name"]),
            "tag": f"settlement-{snap['id']}", "url": f"/?group={snap['group_id']}", "group_id": snap["group_id"],
        }))
    return _emit(ActivityEvent.SETTLEMENT_DELETED, snap["group_id"], actor,
                 f"{first_name(actor)} deleted a settle-up", f"/?group={snap['group_id']}", messages)
