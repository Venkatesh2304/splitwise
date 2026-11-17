import requests
import json
from typing import List, Dict, Any, Optional
from .base_connector import BaseGroceryConnector, GroceryOrder, GroceryItem
from .state import get_swiggy_session

MCP_BASE = "https://mcp.swiggy.com"

from datetime import datetime, timezone, timedelta

IST_TZ = timezone(timedelta(hours=5, minutes=30))

def clean_placed_at(status_text, created_at_raw=None):
    if created_at_raw:
        try:
            if isinstance(created_at_raw, (int, float)) or (isinstance(created_at_raw, str) and created_at_raw.isdigit()):
                val = float(created_at_raw)
                if val > 1e11: val = val / 1000.0
                dt = datetime.fromtimestamp(val, tz=timezone.utc)
            else:
                dt_str = str(created_at_raw).replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            dt_ist = dt.astimezone(IST_TZ)
            return dt_ist.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            pass

    if not status_text:
        return "Recently"
    text = str(status_text)
    if "delivered on " in text.lower():
        parts = text.split("delivered on ")
        if len(parts) > 1:
            rest = parts[1]
            if " by " in rest:
                return rest.split(" by ")[0].strip()
            return rest.strip()
    return text

class SwiggyInstamartConnector(BaseGroceryConnector):
    """Connector for Swiggy Instamart platform using official Swiggy MCP server."""

    @property
    def platform_name(self) -> str:
        return "SWIGGY_INSTAMART"

    def get_auth_status(self, user_context: Optional[Any] = None) -> Dict[str, Any]:
        phone_number = None
        if isinstance(user_context, dict):
            phone_number = user_context.get("phone_number") or user_context.get("phone")
        elif hasattr(user_context, "phone_number"):
            phone_number = getattr(user_context, "phone_number", None)

        session = get_swiggy_session(phone_number)
        token = session.get("access_token")
        return {
            "platform": self.platform_name,
            "is_logged_in": bool(token),
            "phone_number": session.get("phone_number") if token else None
        }

    def fetch_orders(self, force_refresh: bool = False, user_context: Optional[Any] = None) -> List[GroceryOrder]:
        phone_number = None
        if isinstance(user_context, dict):
            phone_number = user_context.get("phone_number") or user_context.get("phone")
        elif hasattr(user_context, "phone_number"):
            phone_number = getattr(user_context, "phone_number", None)

        session = get_swiggy_session(phone_number)
        token = session.get("access_token")
        if not token:
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        rpc_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_orders",
                "arguments": {}
            }
        }

        try:
            res = requests.post(f"{MCP_BASE}/im", headers=headers, json=rpc_payload)
            data = res.json()
            raw_text = data['result']['content'][1]['text']
            orders_raw = json.loads(raw_text).get('orders', [])

            grocery_orders = []
            for ord in orders_raw:
                ord_id = str(ord.get("orderId"))
                total_amt = float(ord.get("totalAmount") or 0.0)
                created_raw = ord.get("createdAt") or ord.get("orderTime") or ord.get("created_at") or ord.get("order_time")
                status_text = clean_placed_at(ord.get("currentStatus"), created_at_raw=created_raw)
                
                bill = ord.get("billDetails", {})
                item_subtotal = float(bill.get("itemTotal") or total_amt)
                other_charges = max(0.0, round(total_amt - item_subtotal, 2))

                items = []
                raw_items = ord.get("items", [])
                
                weights, names, qtys = [], [], []
                for it in raw_items:
                    if isinstance(it, dict):
                        n = it.get("name") or "Instamart Item"
                        q = int(it.get("quantity") or 1)
                        line_p = 0.0
                        for k in ("total", "final_price", "subtotal", "item_total", "amount", "line_total"):
                            try:
                                val = float(it.get(k) or 0.0)
                            except (TypeError, ValueError):
                                val = 0.0
                            if val > 0:
                                line_p = val
                                break
                        if line_p <= 0:
                            for k in ("price", "unit_price", "unitPrice", "item_price", "base_price"):
                                try:
                                    val = float(it.get(k) or 0.0)
                                except (TypeError, ValueError):
                                    val = 0.0
                                if val > 0:
                                    line_p = val * max(1, q)
                                    break
                        if line_p <= 0:
                            line_p = float(max(1, q))
                    else:
                        n = str(it)
                        q = 1
                        line_p = 1.0
                    names.append(n)
                    weights.append(line_p)
                    qtys.append(q)

                target_items = round(total_amt - other_charges, 2)
                if target_items < 0:
                    target_items = total_amt
                    other_charges = 0.0

                from apps.expenses.swiggy_views import rescale_item_lines
                lines = rescale_item_lines(weights, target_items)
                for n, p, q in zip(names, lines, qtys):
                    items.append(GroceryItem(
                        name=n,
                        price=p,
                        quantity=q
                    ))

                other_charges = round(total_amt - sum(it.price for it in items), 2)
                if other_charges < 0:
                    other_charges = 0.0

                grocery_orders.append(GroceryOrder(
                    platform=self.platform_name,
                    order_id=ord_id,
                    placed_at=status_text,
                    total_amount=total_amt,
                    items=items,
                    other_charges=other_charges,
                    store_name="Swiggy Instamart"
                ))

            return grocery_orders
        except Exception as e:
            print(f"Error fetching Swiggy MCP orders: {e}")
            return []
