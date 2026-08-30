from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class GroceryItem:
    """Standardized representation of a single product line item."""
    def __init__(self, name: str, price: float, quantity: int = 1):
        self.name = name
        self.price = float(price)
        self.quantity = int(quantity)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "price": self.price,
            "quantity": self.quantity
        }

class GroceryOrder:
    """Standardized representation of a grocery order across any platform (Blinkit, Swiggy Instamart, Zepto)."""
    def __init__(
        self,
        platform: str,
        order_id: str,
        placed_at: str,
        total_amount: float,
        items: List[GroceryItem],
        other_charges: float = 0.0,
        store_name: Optional[str] = None
    ):
        self.platform = platform
        self.order_id = str(order_id)
        self.placed_at = placed_at
        self.total_amount = float(total_amount)
        self.items = items
        self.other_charges = float(other_charges)
        self.store_name = store_name or platform

    def get_product_names(self) -> List[str]:
        return [it.name for it in self.items]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "order_id": self.order_id,
            "order_type": self.platform,
            "placed_at": self.placed_at,
            "total_amount": self.total_amount,
            "product_names": self.get_product_names(),
            "item_details": [it.to_dict() for it in self.items],
            "other_charges": self.other_charges,
            "store_name": self.store_name
        }

class BaseGroceryConnector(ABC):
    """Abstract Base Class for onboarding quick grocery delivery platforms."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Name of the grocery platform (e.g. BLINKIT, SWIGGY_INSTAMART)."""
        pass

    @abstractmethod
    def get_auth_status(self, user_context: Optional[Any] = None) -> Dict[str, Any]:
        """Returns login authentication status for the platform."""
        pass

    @abstractmethod
    def fetch_orders(self, force_refresh: bool = False, user_context: Optional[Any] = None) -> List[GroceryOrder]:
        """Fetches standardized order history from the platform."""
        pass
