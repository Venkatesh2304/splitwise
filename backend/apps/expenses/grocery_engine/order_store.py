import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from apps.expenses.models import GroceryOrderRecord, GroceryOrderItem

logger = logging.getLogger(__name__)

def _sort_orders_descending(orders_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = datetime.now()
    def get_sort_key(o):
        placed_at = str(o.get("placed_at") or "").strip()
        ord_id = str(o.get("order_id") or "").strip()

        clean_d = placed_at
        if clean_d.lower().startswith("today"):
            clean_d = re.sub(r'^today', now.strftime("%d %b %Y"), clean_d, flags=re.IGNORECASE)
        elif clean_d.lower().startswith("yesterday"):
            clean_d = re.sub(r'^yesterday', datetime.fromtimestamp(now.timestamp() - 86400).strftime("%d %b %Y"), clean_d, flags=re.IGNORECASE)
        elif clean_d and not re.search(r'\d{4}', clean_d):
            clean_d = f"{clean_d} {now.year}"

        clean_d = clean_d.replace(",", "")

        for fmt in ("%d %b %Y %I:%M %p", "%d %b %I:%M %p %Y", "%d %b %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return (datetime.strptime(clean_d, fmt).timestamp(), ord_id)
            except Exception:
                pass

        m = re.search(r'(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})', clean_d)
        if m:
            try:
                return (datetime.strptime(m.group(1), "%d %b %Y").timestamp(), ord_id)
            except Exception:
                pass

        return (0.0, ord_id)

    return sorted(orders_list, key=get_sort_key, reverse=True)

class OrderStoreManager:
    """
    Platform-Agnostic Order Storage & Merging Manager.
    
    Guarantees across all Quick Commerce platforms (Swiggy, Blinkit, etc.):
    1. Order Immutability: Once an order with a given order_id is saved for a user,
       its details are NEVER modified, edited, or overwritten upon refresh.
    2. Additive Persistence: Old orders missing from fresh API responses (e.g. Swiggy 15-day limit)
       remain permanently saved in the Database.
    3. Multi-User & Multi-Platform Isolation.
    4. Chronological Descending Ordering (Newest orders first).
    """

    @staticmethod
    def save_and_merge_orders(user_profile, platform: str, fresh_orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not user_profile:
            return []

        # 1. Iterate through fresh orders and insert NEW ones only (get_or_create)
        for fresh_ord in (fresh_orders or []):
            ord_id = str(fresh_ord.get("order_id") or fresh_ord.get("id") or "").strip()
            if not ord_id or ord_id == "None":
                continue

            placed_at = str(fresh_ord.get("placed_at") or "")
            total_amt = float(fresh_ord.get("total_amount") or fresh_ord.get("amount") or 0.0)
            other_chg = float(fresh_ord.get("other_charges") or 0.0)
            prod_names = fresh_ord.get("product_names") or []
            item_details = fresh_ord.get("item_details") or []

            # get_or_create ensures that if (user, platform, order_id) exists, it is NEVER modified!
            rec, created = GroceryOrderRecord.objects.get_or_create(
                user=user_profile,
                platform=platform,
                order_id=ord_id,
                defaults={
                    "placed_at": placed_at,
                    "total_amount": total_amt,
                    "other_charges": other_chg,
                    "product_names": prod_names,
                    "item_details": item_details,
                    "raw_payload": fresh_ord,
                    "full_order_json": fresh_ord
                }
            )

            # Create individual GroceryOrderItem line items for new order records
            if created and item_details:
                for it in item_details:
                    if isinstance(it, dict):
                        GroceryOrderItem.objects.create(
                            order=rec,
                            name=it.get("name") or "Grocery Item",
                            price=float(it.get("price") or 0.0),
                            quantity=int(it.get("quantity") or 1),
                            item_json=it
                        )
                    elif isinstance(it, str):
                        GroceryOrderItem.objects.create(
                            order=rec,
                            name=it,
                            price=0.0,
                            quantity=1,
                            item_json={"name": it}
                        )

        # 2. Retrieve ALL orders stored in DB for this user & platform
        stored_records = GroceryOrderRecord.objects.filter(
            user=user_profile,
            platform=platform
        ).order_by('-id')

        raw_list = [rec.to_dict() for rec in stored_records]
        return _sort_orders_descending(raw_list)

    @staticmethod
    def get_saved_orders(user_profile, platform: str) -> List[Dict[str, Any]]:
        if not user_profile:
            return []
        stored_records = GroceryOrderRecord.objects.filter(
            user=user_profile,
            platform=platform
        ).order_by('-id')
        raw_list = [rec.to_dict() for rec in stored_records]
        return _sort_orders_descending(raw_list)


