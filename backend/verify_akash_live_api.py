import urllib.request
import json
import sys

def verify_user_orders(user_id=7):
    print(f"=== VERIFYING LIVE ORDERS FOR USER ID={user_id} VIA API ENDPOINTS ===")

    # 1. Blinkit
    blinkit_url = f"http://localhost:8000/api/blinkit/orders/?user_id={user_id}"
    req = urllib.request.Request(blinkit_url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        orders = data.get("orders", [])
        print(f"\n--- Blinkit Orders Count: {len(orders)} ---")
        for idx, o in enumerate(orders, 1):
            tot = float(o.get("total_amount", 0.0))
            other = float(o.get("other_charges", 0.0))
            items = o.get("item_details", [])
            items_sum = sum(float(it.get("price", 0.0)) for it in items)
            diff = round(tot - (items_sum + other), 2)
            print(f"[{idx}] Order #{o.get('order_id')}: Total=₹{tot}, Items Sum=₹{items_sum}, Other Charges=₹{other}, Diff=₹{diff}")
            assert abs(diff) <= 0.01, f"Mismatch in Blinkit order #{o.get('order_id')}! Diff={diff}"

    # 2. Swiggy
    swiggy_url = f"http://localhost:8000/api/swiggy/orders/?user_id={user_id}"
    req = urllib.request.Request(swiggy_url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        orders = data.get("orders", [])
        print(f"\n--- Swiggy Instamart Orders Count: {len(orders)} ---")
        for idx, o in enumerate(orders, 1):
            tot = float(o.get("total_amount", 0.0))
            other = float(o.get("other_charges", 0.0))
            items = o.get("item_details", [])
            items_sum = sum(float(it.get("price", 0.0)) for it in items)
            diff = round(tot - (items_sum + other), 2)
            print(f"[{idx}] Order #{o.get('order_id')}: Total=₹{tot}, Items Sum=₹{items_sum}, Other Charges=₹{other}, Diff=₹{diff}")
            assert abs(diff) <= 0.01, f"Mismatch in Swiggy order #{o.get('order_id')}! Diff={diff}"

    print("\n✅ ALL LIVE ORDERS VERIFIED WITH 0.00 DISCREPANCY!")

if __name__ == "__main__":
    try:
        verify_user_orders()
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
