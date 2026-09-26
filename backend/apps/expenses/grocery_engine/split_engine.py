import json
import re
from typing import Dict, Any, List, Optional
from django.db.models import Q
from django.utils import timezone
from apps.groups.models import Group
from apps.users.models import UserProfile
from apps.expenses.models import Expense, ExpensePayer, ExpenseShare
from apps.expenses.itemized import split_items
from apps.notifications import events

FOOD_KEYWORD_RULES = [
    # Multi-word specific items
    (r'\bgroundnut oil\b', 'Groundnut Oil'),
    (r'\bmustard oil\b', 'Mustard Oil'),
    (r'\bsunflower oil\b', 'Sunflower Oil'),
    (r'\brefined oil\b', 'Cooking Oil'),
    (r'\bcoconut oil\b', 'Coconut Oil'),
    (r'\blady finger\b|\bbhindi\b', 'Lady Finger'),
    (r'\bfrench fries\b', 'Fries'),
    (r'\bsweet corn\b', 'Sweet Corn'),
    (r'\bbiryani kit\b', 'Biryani Kit'),
    (r'\bdark fantasy\b', 'Biscuits'),
    (r'\b(idli\s*&\s*dosa|idli|dosa)\s*batter\b', 'Batter'),
    (r'\bbatter\b', 'Batter'),
    (r'\bred bull\b', 'Energy Drink'),
    (r'\braw pressery\b', 'Juice'),
    (r'\bgarlic bread\b', 'Garlic Bread'),
    (r'\bice cream\b', 'Ice Cream'),
    (r'\bpeanut butter\b', 'Peanut Butter'),

    # Core single-word items
    (r'\bchicken\b', 'Chicken'),
    (r'\bmutton\b', 'Mutton'),
    (r'\bfish\b', 'Fish'),
    (r'\bprawns?\b', 'Prawns'),
    (r'\bsausages?\b', 'Sausages'),
    (r'\bmeat\b', 'Meat'),
    (r'\beggs?\b', 'Eggs'),
    (r'\bmilk\b', 'Milk'),
    (r'\b(curd|dahi|yogurt)\b', 'Curd'),
    (r'\bbread\b', 'Bread'),
    (r'\b(pav|bun|croissant)\b', 'Bakery'),
    (r'\b(banana|kela)s?\b', 'Banana'),
    (r'\b(onion|pyaaz)s?\b', 'Onion'),
    (r'\b(potato|aloo)s?\b', 'Potato'),
    (r'\b(tomato|tamatar)s?\b', 'Tomato'),
    (r'\bghee\b', 'Ghee'),
    (r'\boil\b', 'Oil'),
    (r'\b(rice|sonamasuri|basmati)\b', 'Rice'),
    (r'\bpoha\b', 'Poha'),
    (r'\b(dal|toor|chana|rajma|moong)\b', 'Dal'),
    (r'\bsugar\b', 'Sugar'),
    (r'\bsalt\b', 'Salt'),
    (r'\b(atta|flour|maida|besan)\b', 'Atta'),
    (r'\b(masala|spices?|turmeric|pepper|jeera|cumin)\b', 'Spices'),
    (r'\bpaneer\b', 'Paneer'),
    (r'\bcheese\b', 'Cheese'),
    (r'\bbuttermilk\b', 'Buttermilk'),
    (r'\bbutter\b', 'Butter'),
    (r'\bgranola\b', 'Granola'),
    (r'\bmuesli\b', 'Muesli'),
    (r'\boats\b', 'Oats'),
    (r'\bcorn flakes\b', 'Cereals'),
    (r'\b(chips|crisps|kurkure|nachos)\b', 'Chips'),
    (r'\b(biscuits?|cookies?)\b', 'Biscuits'),
    (r'\bchocolates?\b', 'Chocolate'),
    (r'\b(pizza|burger|sandwich|momos)\b', 'Snacks'),
    (r'\b(noodles?|maggi|pasta)\b', 'Noodles'),
    (r'\bjuice\b', 'Juice'),
    (r'\bcoffee\b', 'Coffee'),
    (r'\btea\b', 'Tea'),
    (r'\b(detergent|surf excel|harpic|vim)\b', 'Cleaning'),
    (r'\b(shampoo|soap|shower gel|body\s*wash|facewash)\b', 'Personal Care'),

    # Specific vegetables & fruits
    (r'\b(carrot|beans|capsicum|cucumber|palak|spinach|mushroom|cauliflower|cabbage|peas|matar|ginger|garlic|coriander|chilli|chili|lemon)\b', 'Vegetables'),
    (r'\b(apple|pomegranate|orange|watermelon|papaya|grapes|avocado)\b', 'Fruits'),

    # Brand fallbacks
    (r'\bmeatizon\b', 'Chicken'),
    (r'\blicious\b', 'Chicken'),
    (r'\bfreshtohome\b', 'Meat'),
]

def extract_top_product_keyword(product_name: str) -> str:
    low = (product_name or '').lower()
    for pattern, display in FOOD_KEYWORD_RULES:
        if re.search(pattern, low):
            return display
    words = re.findall(r'[A-Za-z]+', product_name or '')
    ignore_words = {'pack', 'pcs', 'gm', 'g', 'kg', 'ml', 'l', 'fresh', 'premium', 'daily', 'delight', 'pure', 'classic'}
    filtered = [w for w in words if w.lower() not in ignore_words and len(w) > 1]
    return ' '.join(filtered[:2]).title() if filtered else 'Groceries'

def derive_order_title(platform_name: str, items: Optional[List[Dict[str, Any]]], order_id: Optional[str] = None) -> str:
    plat_low = (platform_name or '').lower()
    if 'swiggy' in plat_low:
        prefix = 'Swiggy'
    elif 'blinkit' in plat_low:
        prefix = 'Blinkit'
    else:
        prefix = (platform_name or 'Order').title()

    if items:
        sorted_items = sorted(items, key=lambda x: float(x.get('price', 0) or 0), reverse=True)
        for it in sorted_items:
            name = it.get('name')
            if name:
                kw = extract_top_product_keyword(name)
                if kw:
                    return f"{prefix}: {kw}"

    if order_id:
        return f"{prefix}: Order #{order_id}"
    return f"{prefix}: Groceries"

class GrocerySplitEngine:
    """Universal Splitting Engine for any Grocery Platform (Blinkit, Swiggy Instamart, Zepto, etc.)."""

    @staticmethod
    def process_split(
        platform_name: str,
        group_id: Optional[int],
        buyer_id: Optional[int],
        order_id: str,
        total_amount: float,
        split_mode: str = "ITEMIZED",
        item_splits_data: Optional[List[Dict[str, Any]]] = None,
        bill_split_data: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        placed_at: Optional[str] = None,
        actor_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes itemized or bill-level splitting, calculates exact proportional fee distributions,
        and saves the expense to the database.
        """
        # 1. Resolve Group
        group = Group.objects.filter(id=group_id).first() if group_id else None
        if not group:
            group = Group.objects.filter(name__icontains="groceries").first() or Group.objects.first()

        if not group:
            raise ValueError("No valid group found for splitting.")

        # 2. Resolve Buyer/Payer
        buyer = UserProfile.objects.filter(id=buyer_id).first() if buyer_id else None
        if not buyer:
            buyer = UserProfile.objects.filter(username="venkatesh").first() or group.members.first()

        if not buyer:
            raise ValueError("No valid buyer profile found.")

        all_members = list(group.members.all())
        member_ids = [m.id for m in all_members]
        owed_amounts = {m_id: 0.0 for m_id in member_ids}

        # Populate products_json_list for both BILL_LEVEL and ITEMIZED splits
        products_json_list = []
        if item_splits_data:
            for it in item_splits_data:
                assigned = it.get("assigned_member_ids", member_ids) if split_mode == "ITEMIZED" else member_ids
                assigned_names = [m.name.split(' ')[0] for m in all_members if m.id in assigned]
                products_json_list.append({
                    "name": it.get("name"),
                    "price": float(it.get("price", 0.0)),
                    "split_type": it.get("split_type", "ALL") if split_mode == "ITEMIZED" else "ALL",
                    "assigned_member_ids": assigned,
                    "assigned_names": assigned_names
                })

        # 3. Calculate Itemized vs Bill-Level Splits
        if split_mode == "BILL_LEVEL":
            b_type = bill_split_data.get("type", "ALL") if bill_split_data else "ALL"
            if b_type == "CUSTOM" and bill_split_data and "custom_amounts" in bill_split_data:
                custom_dict = bill_split_data.get("custom_amounts", {})
                for m_id in member_ids:
                    val = float(custom_dict.get(str(m_id), 0.0) or 0.0)
                    owed_amounts[m_id] = round(val, 2)
                
                diff = round(total_amount - sum(owed_amounts.values()), 2)
                if diff != 0 and buyer.id in owed_amounts:
                    owed_amounts[buyer.id] = round(owed_amounts[buyer.id] + diff, 2)
            else:
                assigned_ids = member_ids
                if bill_split_data and "member_ids" in bill_split_data:
                    assigned_ids = [m_id for m_id in bill_split_data["member_ids"] if m_id in member_ids]
                if not assigned_ids:
                    assigned_ids = member_ids

                n = len(assigned_ids)
                share_per_person = round(total_amount / n, 2)
                for m_id in assigned_ids:
                    owed_amounts[m_id] = share_per_person
                
                diff = round(total_amount - sum(owed_amounts.values()), 2)
                if diff != 0 and assigned_ids:
                    owed_amounts[assigned_ids[0]] = round(owed_amounts[assigned_ids[0]] + diff, 2)

        elif split_mode == "ITEMIZED":
            # Same arithmetic a hand-entered itemised expense uses
            owed_amounts = split_items(total_amount, products_json_list, member_ids, buyer.id)

        # Derive human-readable description if not explicitly customized
        is_generic_or_empty = (
            not description
            or not str(description).strip()
            or bool(re.match(r'^(blinkit|swiggy).*order\s*#', str(description).strip(), re.I))
        )
        if is_generic_or_empty:
            description = derive_order_title(platform_name, products_json_list, order_id)
        else:
            description = str(description).strip()

        # 4. Save Expense to Database
        placed_at_str = str(placed_at or "").strip()
        notes_dict = {
            "platform": platform_name,
            "order_id": str(order_id),
            "split_mode": split_mode,
            "placed_at": placed_at_str,
            "items": products_json_list
        }
        notes_str = json.dumps(notes_dict)

        # A pre-existing split for this order ID makes this a re-split (an edit):
        # snapshot it for the notification before it's replaced.
        order_query = Q(description__icontains=str(order_id)) | Q(notes__icontains=f'"order_id": "{order_id}"') | Q(notes__icontains=str(order_id))
        previous = list(Expense.objects.filter(order_query).order_by('created_at'))
        before = events.snapshot_expense(previous[0]) if previous else None

        # Delete any pre-existing split for this order ID
        Expense.objects.filter(order_query).delete()

        actor = events.resolve_actor(actor_id) or buyer

        expense = Expense.objects.create(
            group=group,
            description=description,
            amount=total_amount,
            category="FOOD",
            split_type="CUSTOM",
            created_by=actor,
            notes=notes_str
        )

        ExpensePayer.objects.create(
            expense=expense,
            user=buyer,
            amount_paid=total_amount
        )

        for m_id, owed in owed_amounts.items():
            user_inst = UserProfile.objects.filter(id=m_id).first()
            if user_inst:
                ExpenseShare.objects.create(
                    expense=expense,
                    user=user_inst,
                    amount_owed=owed,
                    percentage=round((owed / total_amount) * 100, 2) if total_amount > 0 else 0.0
                )

        tag = f"order-{order_id}"
        if before:
            # Keep the original position in the timeline; mark it edited
            Expense.objects.filter(pk=expense.pk).update(
                date=previous[0].date,
                created_at=previous[0].created_at,
                updated_at=timezone.now(),
                updated_by=actor,
            )
            expense.refresh_from_db()
            events.expense_edited(before, expense, actor, tag=tag)
        else:
            events.expense_added(expense, actor, tag=tag)

        return {
            "message": f"Successfully split '{description}' into group '{group.name}'!",
            "expense_id": expense.id,
            "owed_breakdown": owed_amounts
        }

    @staticmethod
    def remove_split(order_id: str, actor_id: Optional[int] = None) -> Dict[str, Any]:
        """Deletes any expense corresponding to the given order ID."""
        order_query = Q(description__icontains=str(order_id)) | Q(notes__icontains=f'"order_id": "{order_id}"') | Q(notes__icontains=str(order_id))
        expenses = Expense.objects.filter(order_query)
        snapshots = [events.snapshot_expense(e) for e in expenses]
        deleted_count, _ = expenses.delete()
        actor = events.resolve_actor(actor_id)
        for snap in snapshots:
            events.expense_deleted(snap, actor, tag=f"order-{order_id}")
        return {
            "ok": True,
            "message": f"Removed split for order #{order_id} ({deleted_count} expense deleted)."
        }
