import requests
import json
from typing import List, Dict, Any, Optional
from .base_connector import BaseGroceryConnector, GroceryOrder, GroceryItem
from .state import get_swiggy_session

MCP_BASE = "https://mcp.swiggy.com"

def clean_placed_at(status_text):
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
                status_text = clean_placed_at(ord.get("currentStatus"))
                
                bill = ord.get("billDetails", {})
                item_subtotal = float(bill.get("itemTotal") or total_amt)
                other_charges = max(0.0, round(total_amt - item_subtotal, 2))

                items = []
                raw_items = ord.get("items", [])
                num_items = max(1, len(raw_items))
                avg_price = round(item_subtotal / num_items, 2)

                for it in raw_items:
                    items.append(GroceryItem(
                        name=it.get("name"),
                        price=avg_price,
                        quantity=int(it.get("quantity") or 1)
                    ))

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
