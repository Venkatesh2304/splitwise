from typing import Dict, List, Optional
from .base_connector import BaseGroceryConnector
from .blinkit_connector import BlinkitConnector
from .swiggy_connector import SwiggyInstamartConnector

class GroceryPlatformRegistry:
    """Central Pluggable Registry for all Grocery Delivery Platforms."""
    
    _connectors: Dict[str, BaseGroceryConnector] = {}

    @classmethod
    def register(cls, connector: BaseGroceryConnector):
        cls._connectors[connector.platform_name.upper()] = connector

    @classmethod
    def get(cls, platform_name: str) -> Optional[BaseGroceryConnector]:
        return cls._connectors.get(platform_name.upper())

    @classmethod
    def list_platforms(cls) -> List[str]:
        return list(cls._connectors.keys())

# Auto-register supported platforms
GroceryPlatformRegistry.register(BlinkitConnector())
GroceryPlatformRegistry.register(SwiggyInstamartConnector())
