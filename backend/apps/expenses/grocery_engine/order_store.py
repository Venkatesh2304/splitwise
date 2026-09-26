import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from apps.expenses.models import GroceryOrderRecord, GroceryOrderItem

logger = logging.getLogger(__name__)

IST_TZ = timezone(timedelta(hours=5, minutes=30))

def resolve_placed_at_ist(placed_at_str: str, fresh_ord: Optional[Dict[str, Any]] = None) -> str:
    s = str(placed_at_str or "").strip()
    now_ist = datetime.now(IST_TZ)

    # 1. If raw payload has createdAt / orderTime in UTC, format in IST
    if fresh_ord:
        raw_payload = fresh_ord.get("full_order_json") or fresh_ord.get("raw_payload") or fresh_ord
        raw_time = raw_payload.get("createdAt") or raw_payload.get("orderTime") or raw_payload.get("created_at") or raw_payload.get("order_time")
        if raw_time:
            try:
                if isinstance(raw_time, (int, float)) or (isinstance(raw_time, str) and raw_time.isdigit()):
                    val = float(raw_time)
                    if val > 1e11: val = val / 1000.0
                    dt = datetime.fromtimestamp(val, tz=timezone.utc)
                else:
                    dt = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(IST_TZ).strftime("%d %b %Y, %I:%M %p")
            except Exception:
                pass

    # 2. Resolve relative keywords like "today" or "yesterday"
    if s.lower().startswith("today"):
        s = re.sub(r'^today', now_ist.strftime("%d %b %Y"), s, flags=re.IGNORECASE)
    elif s.lower().startswith("yesterday"):
        yest = now_ist - timedelta(days=1)
        s = re.sub(r'^yesterday', yest.strftime("%d %b %Y"), s, flags=re.IGNORECASE)

    return s

def _sort_orders_descending(orders_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = datetime.now(IST_TZ)
    def get_sort_key(o):
        placed_at = str(o.get("placed_at") or "").strip()
        ord_id = str(o.get("order_id") or "").strip()
        full_json = o.get("full_order_json") or o.get("raw_payload") or {}

        # 1. Try ISO createdAt / orderTime from raw payload first
        created_at_raw = full_json.get("createdAt") or full_json.get("orderTime") or full_json.get("order_time") or full_json.get("created_at")
        if created_at_raw:
            try:
                dt_str = str(created_at_raw).replace("Z", "+00:00")
                return (datetime.fromisoformat(dt_str).timestamp(), ord_id)
            except Exception:
                pass

        # 2. Try placed_at date string
        clean_d = placed_at
        if clean_d.lower().startswith("today"):
            clean_d = re.sub(r'^today', now.strftime("%d %b %Y"), clean_d, flags=re.IGNORECASE)
        elif clean_d.lower().startswith("yesterday"):
            clean_d = re.sub(r'^yesterday', datetime.fromtimestamp(now.timestamp() - 86400).strftime("%d %b %Y"), clean_d, flags=re.IGNORECASE)
        elif clean_d and not re.search(r'\d{4}', clean_d):
            clean_d = f"{clean_d} {now.year}"

        clean_d = clean_d.replace(",", "")

        for fmt in ("%d %b %Y %I:%M %p", "%d %b %I:%M %p %Y", "%d %b %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
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
    1. Robust Order Persistence & Updates: Fresh orders insert new records or update transient status text/items.
    2. Additive Persistence: Old orders missing from fresh API responses (e.g. Swiggy MCP limits) remain permanently saved in DB.
    3. Multi-User & Multi-Platform Isolation.
    4. Chronological Descending Ordering (Newest orders first).
    """

    @staticmethod
    def save_and_merge_orders(user_profile, platform: str, fresh_orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not user_profile:
            return []

        # 1. Iterate through fresh orders and insert NEW ones or update existing transient ones
        for fresh_ord in (fresh_orders or []):
            ord_id = str(fresh_ord.get("order_id") or fresh_ord.get("id") or "").strip()
            if not ord_id or ord_id == "None":
                continue

            placed_at = resolve_placed_at_ist(fresh_ord.get("placed_at"), fresh_ord)
            total_amt = float(fresh_ord.get("total_amount") or fresh_ord.get("amount") or 0.0)
            other_chg = float(fresh_ord.get("other_charges") or 0.0)
            prod_names = fresh_ord.get("product_names") or []
            item_details = fresh_ord.get("item_details") or []

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

            if not created:
                updated = False
                transient_keywords = ["confirmed", "placed", "transit", "recently", "pending"]
                is_existing_transient = not rec.placed_at or any(kw in str(rec.placed_at).lower() for kw in transient_keywords) or not re.search(r'\d', str(rec.placed_at))
                
                if placed_at and (is_existing_transient or placed_at != rec.placed_at):
                    if not any(kw in str(placed_at).lower() for kw in transient_keywords) or is_existing_transient:
                        rec.placed_at = placed_at
                        updated = True

                if item_details and (not rec.item_details or len(rec.item_details) < len(item_details)):
                    rec.item_details = item_details
                    rec.product_names = prod_names or rec.product_names
                    updated = True

                if total_amt > 0 and (rec.total_amount == 0 or abs(rec.total_amount - total_amt) > 0.01):
                    rec.total_amount = total_amt
                    updated = True

                if fresh_ord:
                    rec.full_order_json = fresh_ord
                    rec.raw_payload = fresh_ord
                    updated = True

                if updated:
                    rec.save()

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


