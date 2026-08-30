from typing import List, Dict, Any, Optional
from .base_connector import BaseGroceryConnector, GroceryOrder, GroceryItem
from .state import get_blinkit_session

class BlinkitConnector(BaseGroceryConnector):
    """Connector for Blinkit platform."""

    @property
    def platform_name(self) -> str:
        return "BLINKIT"

    def get_auth_status(self, user_context: Optional[Any] = None) -> Dict[str, Any]:
        phone_number = None
        if isinstance(user_context, dict):
            phone_number = user_context.get("phone_number") or user_context.get("phone")
        elif hasattr(user_context, "phone_number"):
            phone_number = getattr(user_context, "phone_number", None)

        session = get_blinkit_session(phone_number)
        access_token = session.get("access_token")
        return {
            "platform": self.platform_name,
            "is_logged_in": bool(access_token),
            "phone_number": session.get("phone_number") if access_token else None
        }

    def fetch_orders(self, force_refresh: bool = False, user_context: Optional[Any] = None) -> List[GroceryOrder]:
        from apps.expenses.blinkit_views import fetch_blinkit_orders_internal
        phone_number = None
        if isinstance(user_context, dict):
            phone_number = user_context.get("phone_number") or user_context.get("phone")
        elif hasattr(user_context, "phone_number"):
            phone_number = getattr(user_context, "phone_number", None)

        orders_data = fetch_blinkit_orders_internal(phone_number=phone_number, force_refresh=force_refresh)
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
