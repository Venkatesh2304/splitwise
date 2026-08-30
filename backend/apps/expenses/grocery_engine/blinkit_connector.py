from typing import List, Dict, Any, Optional
from .base_connector import BaseGroceryConnector, GroceryOrder, GroceryItem
from .state import BLINKIT_SESSION

class BlinkitConnector(BaseGroceryConnector):
    """Connector for Blinkit platform."""

    @property
    def platform_name(self) -> str:
        return "BLINKIT"

    def get_auth_status(self, user_context: Optional[Any] = None) -> Dict[str, Any]:
        access_token = BLINKIT_SESSION.get("access_token")
        phone_number = BLINKIT_SESSION.get("phone_number", "6382247549")
        return {
            "platform": self.platform_name,
            "is_logged_in": bool(access_token),
            "phone_number": phone_number if access_token else None
        }

    def fetch_orders(self, force_refresh: bool = False, user_context: Optional[Any] = None) -> List[GroceryOrder]:
        from apps.expenses.blinkit_views import fetch_blinkit_orders_internal
        orders_data = fetch_blinkit_orders_internal(force_refresh=force_refresh)
        grocery_orders = []

        for ord in orders_data:
            items = []
            for it in ord.get("item_details", []):
                items.append(GroceryItem(
                    name=it.get("name"),
                    price=float(it.get("price", 0.0)),
                    quantity=int(it.get("quantity", 1))
                ))

            grocery_orders.append(GroceryOrder(
                platform=self.platform_name,
                order_id=str(ord.get("order_id")),
                placed_at=ord.get("placed_at", "Recently"),
                total_amount=float(ord.get("total_amount", 0.0)),
                items=items,
                other_charges=float(ord.get("other_charges", 0.0)),
                store_name="Blinkit"
            ))

        return grocery_orders
