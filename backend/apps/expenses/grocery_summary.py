import json
import re
from collections import defaultdict, Counter
from datetime import datetime
from apps.expenses.models import Expense
from apps.expenses.itemized import (
    assigned_ids as resolve_assigned_ids,
    extract_expense_items,
    get_expense_source_info,
    ALL, PERSONAL, SPECIFIC
)

# Deterministic Product Keyword Rules: (Display Name, [keywords])
DETERMINISTIC_PRODUCT_RULES = [
    ('Chicken & Meat', ['chicken', 'meat', 'mutton', 'fish', 'prawn', 'licious', 'meatizon', 'freshtohome', 'sausage']),
    ('Eggs', ['egg', 'eggs']),
    ('Milk', ['milk']),
    ('Curd & Yogurt', ['curd', 'dahi', 'yogurt']),
    ('Idli & Dosa Batter', ['batter', 'idli', 'dosa']),
    ('Bread & Bakery', ['bread', 'pav', 'bun', 'croissant', 'rusk']),
    ('Bananas', ['banana', 'kela']),
    ('Onions', ['onion', 'pyaaz']),
    ('Potatoes', ['potato', 'aloo']),
    ('Tomatoes', ['tomato']),
    ('Vegetables (Other)', ['lady finger', 'bhindi', 'ginger', 'garlic', 'carrot', 'beans', 'lemon', 'chilli', 'chili', 'coriander', 'cucumber', 'capsicum', 'palak', 'spinach', 'coconut', 'matar', 'peas', 'mushroom', 'beetroot', 'cauliflower', 'cabbage', 'sweet corn', 'mint']),
    ('Fruits (Other)', ['apple', 'pomegranate', 'orange', 'watermelon', 'papaya', 'grapes', 'avocado']),
    ('Cooking Oil & Ghee', ['groundnut oil', 'mustard oil', 'sunflower oil', 'refined oil', 'oil', 'ghee']),
    ('Rice & Grains', ['rice', 'sonamasuri', 'biryani kit', 'poha']),
    ('Dal & Pulses', ['dal', 'toor', 'chana', 'rajma', 'moong', 'peanuts']),
    ('Atta, Flour & Spices', ['atta', 'flour', 'salt', 'sugar', 'masala', 'turmeric', 'pepper', 'jeera', 'spices', 'cumin', 'mustard', 'sauce', 'ketchup', 'soya', 'noodle', 'maggi', 'pasta', 'kasuri methi']),
    ('Granola & Cereals', ['granola', 'muesli', 'corn flakes', 'oats']),
    ('Chips & Crisps', ['bingo', "lay's", 'lays', 'chips', 'crisps', 'kurkure', 'nachos']),
    ('Biscuits, Cookies & Sweets', ['cookie', 'cookies', 'biscuit', 'biscuits', 'chocolate', 'chocolates', 'dark fantasy', 'oreo', 'kitkat', 'munch', 'wafer', 'candy', 'mithai']),
    ('Beverages & Soft Drinks', ['coca-cola', 'coke', 'pepsi', 'juice', 'soda', 'coffee', 'tea', 'red bull', 'sugarcane', 'water', 'sprite', 'thums up', 'drink', 'beverage', 'enerzal', 'bournvita', 'horlicks', 'raw pressery', 'beer', 'cocktail', 'cocktails', 'wine']),
    ('Dining & Fast Food', ['pizza', 'burger', 'sandwich', 'shawarma', 'roll', 'fries', 'french fries', 'momos', 'noodles', 'fried rice', 'thali', 'curry', 'roti', 'naan', 'tikka', 'kebab', 'starters']),
    ('Paneer, Cheese & Butter', ['paneer', 'cheese', 'butter', 'buttermilk']),
    ('Cleaning & Household', ['detergent', 'garbage bag', 'dishwash', 'vim', 'harpic', 'surf excel', 'cleaner', 'spray', 'scrub', 'sponge', 'laundry', 'pochha', 'cloth', 'lighter', 'clip', 'tissue', 'foil', 'freshener']),
    ('Personal Care & Grooming', ['shampoo', 'conditioner', 'soap', 'shower gel', 'body wash', 'bodywash', 'face wash', 'facewash', 'serum', 'lotion', 'cream', 'deodorant', 'perfume', 'toothbrush', 'toothpaste', 'colgate', 'tresemme', 'fiama', 'joy', 'sanitary', 'pad', 'handwash', 'dettol', 'lux', 'shaving', 'razor', 'dove', 'sample']),
    ('Electronics & Accessories', ['portronics', 'power cord', 'power plate', 'mobile cover', 'cable', 'charger', 'battery', 'clean m 8']),
    ('Apparel & Lifestyle', ['shorts', 'trunks', 'sliders', 'lamp', 'creatine', 'dates', 'silver voucher'])
]

# Deterministic Category Rules: (Display Name, [keywords])
DETERMINISTIC_CATEGORY_RULES = [
    ('Meat, Poultry & Eggs', ['chicken', 'meat', 'mutton', 'fish', 'prawn', 'licious', 'meatizon', 'freshtohome', 'sausage', 'egg', 'eggs']),
    ('Dairy, Breakfast & Batters', ['milk', 'curd', 'dahi', 'yogurt', 'butter', 'paneer', 'cheese', 'batter', 'idli', 'dosa', 'bread', 'pav', 'granola', 'oats', 'muesli', 'corn flakes', 'honey', 'jam', 'peanut butter', 'buttermilk', 'lassi']),
    ('Dining, Meals & Fast Food', ['pizza', 'burger', 'sandwich', 'shawarma', 'roll', 'fries', 'french fries', 'momos', 'noodles', 'fried rice', 'thali', 'curry', 'roti', 'naan', 'tikka', 'kebab', 'starters', 'meal', 'restaurant']),
    ('Fresh Fruits & Vegetables', ['onion', 'potato', 'tomato', 'banana', 'apple', 'kela', 'pyaaz', 'aloo', 'lady finger', 'bhindi', 'ginger', 'garlic', 'carrot', 'beans', 'lemon', 'chilli', 'chili', 'coriander', 'cucumber', 'capsicum', 'palak', 'spinach', 'coconut', 'matar', 'peas', 'mushroom', 'beetroot', 'cauliflower', 'cabbage', 'sweet corn', 'mint', 'pomegranate', 'orange', 'watermelon', 'papaya', 'grapes', 'avocado']),
    ('Staples, Oils & Spices', ['oil', 'ghee', 'rice', 'atta', 'flour', 'dal', 'salt', 'sugar', 'masala', 'turmeric', 'pepper', 'jeera', 'biryani kit', 'paste', 'spices', 'cumin', 'mustard', 'sauce', 'ketchup', 'soya', 'noodle', 'maggi', 'pasta', 'poha', 'besan', 'maida', 'peanuts', 'kasuri methi']),
    ('Snacks, Biscuits & Sweets', ['bingo', "lay's", 'lays', 'chips', 'crisps', 'cookie', 'cookies', 'biscuit', 'biscuits', 'chocolate', 'chocolates', 'namkeen', 'kurkure', 'dark fantasy', 'oreo', 'kitkat', 'munch', 'snack', 'mixture', 'rusk', 'wafer', 'candy', 'mithai', 'murukku', 'popcorn', 'dessert', 'fudge', 'ice cream']),
    ('Beverages & Drinks', ['coca-cola', 'coke', 'pepsi', 'juice', 'soda', 'coffee', 'tea', 'red bull', 'sugarcane', 'water', 'sprite', 'thums up', 'drink', 'beverage', 'enerzal', 'raw pressery', 'tender coconut', 'beer', 'cocktail', 'cocktails', 'wine']),
    ('Household & Cleaning', ['detergent', 'garbage bag', 'dishwash', 'vim', 'harpic', 'surf excel', 'cleaner', 'spray', 'scrub', 'sponge', 'laundry', 'pochha', 'cloth', 'lighter', 'clip', 'tissue', 'foil', 'freshener']),
    ('Personal Care & Hygiene', ['shampoo', 'conditioner', 'soap', 'shower gel', 'body wash', 'bodywash', 'face wash', 'facewash', 'serum', 'lotion', 'cream', 'deodorant', 'perfume', 'toothbrush', 'toothpaste', 'colgate', 'tresemme', 'fiama', 'joy', 'sanitary', 'pad', 'handwash', 'dettol', 'lux', 'shaving', 'razor', 'dove', 'sample']),
    ('Electronics & Lifestyle', ['portronics', 'power cord', 'power plate', 'mobile cover', 'cable', 'charger', 'battery', 'clean m 8', 'shorts', 'trunks', 'sliders', 'lamp', 'creatine', 'dates', 'silver voucher'])
]

def match_product_keyword(name):
    low = (name or '').lower()
    for label, keywords in DETERMINISTIC_PRODUCT_RULES:
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', low) or (len(kw) > 4 and kw in low):
                return label
    return 'Other Everyday Items'

def match_category(name):
    low = (name or '').lower()
    for label, keywords in DETERMINISTIC_CATEGORY_RULES:
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', low) or (len(kw) > 4 and kw in low):
                return label
    return 'Other Everyday Essentials'

def build_grocery_summary(group=None, user_id=None, month=None):
    """
    Builds deterministic category and product-keyword spend summaries.
    
    When Total Group is requested:
      Shows total group spend on each category and product keyword.
      
    When a specific user is requested:
      Shows the SPLIT ON THAT USER (his exact share for each category and product keyword
      based on assigned members in the itemized split).
    """
    members = {}
    group_expenses = []
    
    if group:
        members = {m.id: m.name for m in group.members.all()}
        group_expenses = list(Expense.objects.filter(group=group).order_by('-date', '-created_at'))
    else:
        group_expenses = list(Expense.objects.all().order_by('-date', '-created_at'))
        all_payers = set()
        for e in group_expenses:
            for p in e.payers.all(): all_payers.add(p.user)
            for s in e.shares.all(): all_payers.add(s.user)
        members = {u.id: u.name for u in all_payers}
        
    available_users = [
        {"id": uid, "name": uname}
        for uid, uname in sorted(members.items(), key=lambda x: x[1])
    ]
    
    target_uid = None
    active_user_name = "Total Group"
    if user_id and str(user_id).lower() not in ('all', 'none', ''):
        try:
            target_uid = int(user_id)
            if target_uid in members:
                active_user_name = members[target_uid]
        except (ValueError, TypeError):
            pass

    # Collect available months from grocery expenses
    month_counts = Counter()
    grocery_expenses_with_items = []
    
    for e in group_expenses:
        items = extract_expense_items(e)
        if items:
            m_str = e.date.strftime('%Y-%m')
            month_counts[m_str] += 1
            grocery_expenses_with_items.append((e, items))

    available_months = sorted(month_counts.keys(), reverse=True)
    
    # Filter by month if specified and not 'all'
    if month and str(month).lower() not in ('all', 'none', ''):
        filtered = []
        for e, items in grocery_expenses_with_items:
            if e.date.strftime('%Y-%m') == str(month):
                filtered.append((e, items))
        grocery_expenses_with_items = filtered

    # Aggregations
    total_spend = 0.0
    total_items = 0
    orders_counted = set()
    
    cat_data = defaultdict(lambda: {
        'spend': 0.0,
        'quantity': 0,
        'item_count': 0,
        'products': Counter(),
        'top_by_spend': defaultdict(float)
    })
    
    prod_data = defaultdict(lambda: {
        'spend': 0.0,
        'quantity': 0,
        'item_count': 0,
        'products': Counter(),
        'top_by_spend': defaultdict(float)
    })
    
    for e, items in grocery_expenses_with_items:
        expense_shares = {s.user_id: float(s.amount_owed) for s in e.shares.all()}
        fallback_members = list(expense_shares.keys()) if expense_shares else list(members.keys())
        payer_id = e.created_by_id or (fallback_members[0] if fallback_members else None)
        
        for it in items:
            name = str(it.get('name') or 'Unknown').strip()
            price = float(it.get('price') or 0.0)
            qty = int(it.get('quantity') or 1)
            
            assigned_ids = resolve_assigned_ids(it, fallback_members, payer_id)
            if not assigned_ids:
                assigned_ids = fallback_members
                
            cat = match_category(name)
            pkw = match_product_keyword(name)
            
            if target_uid is None:
                # Total Group spend on this item
                total_spend += price
                total_items += 1
                orders_counted.add(e.id)
                
                cat_data[cat]['spend'] += price
                cat_data[cat]['quantity'] += qty
                cat_data[cat]['item_count'] += 1
                cat_data[cat]['products'][name] += qty
                cat_data[cat]['top_by_spend'][name] += price
                
                prod_data[pkw]['spend'] += price
                prod_data[pkw]['quantity'] += qty
                prod_data[pkw]['item_count'] += 1
                prod_data[pkw]['products'][name] += qty
                prod_data[pkw]['top_by_spend'][name] += price
            else:
                # Split ON target user for this item (Consumer summary)
                if target_uid in assigned_ids:
                    user_share = price / len(assigned_ids)
                    user_qty = round(qty / len(assigned_ids), 2)
                    
                    total_spend += user_share
                    total_items += 1
                    orders_counted.add(e.id)
                    
                    cat_data[cat]['spend'] += user_share
                    cat_data[cat]['quantity'] += user_qty
                    cat_data[cat]['item_count'] += 1
                    cat_data[cat]['products'][name] += user_qty
                    cat_data[cat]['top_by_spend'][name] += user_share
                    
                    prod_data[pkw]['spend'] += user_share
                    prod_data[pkw]['quantity'] += user_qty
                    prod_data[pkw]['item_count'] += 1
                    prod_data[pkw]['products'][name] += user_qty
                    prod_data[pkw]['top_by_spend'][name] += user_share

    # Format Category Results
    categories = []
    for cat_name, data in sorted(cat_data.items(), key=lambda kv: kv[1]['spend'], reverse=True):
        top_items = [
            {"name": p_name, "quantity": data['products'][p_name], "spend": round(spend_amt, 2)}
            for p_name, spend_amt in sorted(data['top_by_spend'].items(), key=lambda x: -x[1])[:3]
        ]
        spend_val = round(data['spend'], 2)
        pct = round((spend_val / total_spend * 100), 1) if total_spend > 0 else 0.0
        categories.append({
            "name": cat_name,
            "spend": spend_val,
            "quantity": round(data['quantity'], 2),
            "item_count": data['item_count'],
            "percent": pct,
            "top_items": top_items
        })

    # Format Product Keyword Results
    products = []
    for kw_name, data in sorted(prod_data.items(), key=lambda kv: kv[1]['spend'], reverse=True):
        top_items = [
            {"name": p_name, "quantity": data['products'][p_name], "spend": round(spend_amt, 2)}
            for p_name, spend_amt in sorted(data['top_by_spend'].items(), key=lambda x: -x[1])[:3]
        ]
        spend_val = round(data['spend'], 2)
        pct = round((spend_val / total_spend * 100), 1) if total_spend > 0 else 0.0
        products.append({
            "keyword": kw_name,
            "spend": spend_val,
            "quantity": round(data['quantity'], 2),
            "item_count": data['item_count'],
            "percent": pct,
            "top_items": top_items
        })

    return {
        "total_spend": round(total_spend, 2),
        "total_orders": len(orders_counted),
        "total_items": total_items,
        "filter_type": "user_split" if target_uid else "group_total",
        "active_user": {
            "id": target_uid,
            "name": active_user_name
        },
        "selected_month": month or "all",
        "available_users": available_users,
        "available_months": available_months,
        "categories": categories,
        "products": products
    }
