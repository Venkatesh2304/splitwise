import json
import time
import uuid
import re
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from curl_cffi import requests

from apps.groups.models import Group
from apps.users.models import UserProfile
from apps.expenses.models import Expense, ExpensePayer, ExpenseShare
from apps.expenses.grocery_engine import GrocerySplitEngine
from apps.expenses.grocery_engine.state import BLINKIT_SESSION, BLINKIT_ORDER_CACHE, CACHE_TTL_SECONDS

REQ_KEY = "c0e6868e-1180-400c-be51-f473479f1f0a"

def get_blinkit_api_headers(include_auth_key=True):
    if not BLINKIT_SESSION.get("device_id"):
        BLINKIT_SESSION["device_id"] = uuid.uuid4().hex[:16]
    if not BLINKIT_SESSION.get("session_uuid"):
        BLINKIT_SESSION["session_uuid"] = str(uuid.uuid4())

    headers = {
        "app_client": "consumer_web",
        "platform": "desktop_web",
        "web_app_version": "1008010016",
        "rn_bundle_version": "1009003012",
        "app_version": "52434332",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "req_key": REQ_KEY,
        "device_id": BLINKIT_SESSION["device_id"],
        "session_uuid": BLINKIT_SESSION["session_uuid"],
        "referer": "https://blinkit.com/",
        "origin": "https://blinkit.com"
    }

    if include_auth_key and BLINKIT_SESSION.get("auth_key"):
        headers["auth_key"] = BLINKIT_SESSION["auth_key"]

    if BLINKIT_SESSION.get("access_token"):
        headers["access_token"] = BLINKIT_SESSION["access_token"]

    return headers

def ensure_blinkit_auth_key():
    if BLINKIT_SESSION.get("auth_key"):
        return BLINKIT_SESSION["auth_key"]

    try:
        headers = get_blinkit_api_headers(include_auth_key=False)
        url = "https://blinkit.com/v2/accounts/auth_key/"
        res = requests.get(url, headers=headers, impersonate="chrome110", timeout=8)
        if res.status_code == 200:
            data = res.json()
            auth_key = data.get("auth_key")
            if auth_key:
                BLINKIT_SESSION["auth_key"] = auth_key
                return auth_key
    except Exception as e:
        print(f"Error fetching Blinkit auth_key: {e}")

    return None

def parse_reorder_ids(deeplink):
    if not deeplink: return []
    m = re.search(r'product_ids=([\d,]+)', str(deeplink))
    if not m: return []
    return [int(x) for x in m.group(1).split(',') if x.isdigit()]

def text_of(v):
    if isinstance(v, str): return v
    if isinstance(v, dict) and 'text' in v: return v['text']
    return None

def as_num(v):
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str):
        cleaned = re.sub(r'[^\d.]', '', v)
        try: return float(cleaned)
        except: pass
    return 0.0

def fetch_exact_blinkit_order_details(order_id):
    """Fetches exact individual item prices, product names, and bill charges directly from Blinkit order_details API."""
    try:
        ensure_blinkit_auth_key()
        headers = get_blinkit_api_headers()
        url = f"https://blinkit.com/v1/layout/order_details/{order_id}"
        res = requests.post(url, headers=headers, json={}, impersonate="chrome110", timeout=10)
        if res.status_code != 200:
            return [], 0.0

        snippets = res.json().get("response", {}).get("snippets", [])
        item_details = []
        other_charges = 0.0

        for s in snippets:
            wtype = s.get("widget_type")
            s_data = s.get("data", {})

            if wtype in ["z_v3_image_text_snippet_type_30", "v2_image_text_snippet_type_30"]:
                p_name = s_data.get("title", {}).get("text")
                sub3 = s_data.get("subtitle3", {}).get("text", "")

                price = 0.0
                if p_name and sub3:
                    price_match = re.findall(r"₹\s*(\d+(?:\.\d+)?)", sub3)
                    if price_match:
                        price = float(price_match[-1])
                    item_details.append({"name": p_name, "price": price, "quantity": 1})

            elif wtype == "cart_bill_item":
                left = s_data.get("left_header", {}).get("text", "")
                right = s_data.get("right_header", {}).get("text", "")
                if "handling" in left.lower() or "delivery" in left.lower():
                    val_match = re.search(r"(\d+(?:\.\d+)?)", right)
                    if val_match:
                        other_charges += float(val_match.group(1))

        return item_details, other_charges
    except Exception as e:
        print(f"Error fetching exact details for order {order_id}: {e}")
        return [], 0.0

def extract_blinkit_orders_from_sdui(root):
    orders = []
    seen = set()

    def visit(node):
        if not node or not isinstance(node, (dict, list)): return
        if id(node) in seen: return
        seen.add(id(node))

        if isinstance(node, list):
            for item in node: visit(item)
            return

        if node.get('widget_type') == 'order_history_container_vr':
            common = node.get('tracking', {}).get('common_attributes', {})
            names = []
            ids = set()
            total = 0.0
            placed_at = 'Recently'

            def inner(n):
                nonlocal total, placed_at
                if not n or not isinstance(n, (dict, list)): return
                if isinstance(n, list):
                    for item in n: inner(item)
                    return
                
                acc = n.get('image', {}).get('accessibility_text', {}).get('text')
                if isinstance(acc, str): names.append(acc)
                
                sub = text_of(n.get('left_underlined_subtitle'))
                if sub and total == 0.0: total = as_num(sub)

                ts = text_of(n.get('subtitle'))
                if ts and re.search(r'\d', ts) and placed_at == 'Recently': placed_at = ts

                for dl in [n.get('click_action', {}).get('blinkit_deeplink', {}).get('url'),
                           n.get('bottom_button', {}).get('click_action', {}).get('blinkit_deeplink', {}).get('url')]:
                    for pid in parse_reorder_ids(dl): ids.add(pid)

                for k, v in n.items(): inner(v)

            inner(node)
            order_id = str(common.get('order_id') or common.get('id') or f'BLINKIT_{len(orders)+1}')
            
            # Fetch 100% real product item names & exact prices via order_details API
            exact_items, other_chg = fetch_exact_blinkit_order_details(order_id)

            if not exact_items:
                prod_names = list(dict.fromkeys(names))
                exact_items = []
                if prod_names:
                    approx_price = round(total / len(prod_names), 2)
                    for pname in prod_names:
                        exact_items.append({"name": pname, "price": approx_price, "quantity": 1})
                    other_chg = max(0.0, round(total - (approx_price * len(prod_names)), 2))
            else:
                prod_names = [it["name"] for it in exact_items]

            orders.append({
                'order_id': order_id,
                'placed_at': placed_at,
                'total_amount': total,
                'product_names': prod_names,
                'item_details': exact_items,
                'other_charges': other_chg
            })
            return

        for k, v in node.items(): visit(v)

    visit(root)
    return orders

def fetch_blinkit_orders_internal(force_refresh=False):
    now = time.time()
    if not force_refresh and BLINKIT_ORDER_CACHE["data"] and (now - BLINKIT_ORDER_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        return BLINKIT_ORDER_CACHE["data"]

    access_token = BLINKIT_SESSION.get("access_token")
    if not access_token:
        orders_list = []
    else:
        try:
            ensure_blinkit_auth_key()
            headers = get_blinkit_api_headers()
            url = "https://blinkit.com/v1/layout/order_history"
            res = requests.post(url, headers=headers, json={}, impersonate="chrome110", timeout=10)
            if res.status_code == 200:
                parsed_orders = extract_blinkit_orders_from_sdui(res.json())
                orders_list = parsed_orders
            else:
                orders_list = []
        except Exception as e:
            print(f"Error fetching Blinkit orders: {e}")
            orders_list = []

    BLINKIT_ORDER_CACHE["data"] = orders_list
    BLINKIT_ORDER_CACHE["timestamp"] = now
    return orders_list

@api_view(['GET'])
def blinkit_status(request):
    return Response(BLINKIT_SESSION, status=status.HTTP_200_OK)

@api_view(['POST'])
def blinkit_send_otp(request):
    raw_phone = request.data.get("phone_number") or request.data.get("phone") or ""
    phone_number = str(raw_phone).strip()
    if not phone_number or len(phone_number) < 10:
        return Response({"error": "Invalid phone number.", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)

    BLINKIT_SESSION["phone_number"] = phone_number

    try:
        ensure_blinkit_auth_key()
        headers = get_blinkit_api_headers()
        url = "https://blinkit.com/v2/accounts/"
        res = requests.post(url, data={"user_phone": phone_number}, headers=headers, impersonate="chrome110", timeout=10)

        if res.status_code == 200:
            data = res.json()
            if data.get("sms_sent") or data.get("success"):
                return Response({"message": f"OTP sent to {phone_number} via SMS.", "success": True, "ok": True}, status=status.HTTP_200_OK)
            else:
                return Response({"error": data.get("message") or "Failed to send OTP.", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": f"Blinkit API error (Status {res.status_code})", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e), "success": False, "ok": False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def blinkit_verify_otp(request):
    raw_phone = request.data.get("phone_number") or request.data.get("phone") or BLINKIT_SESSION.get("phone_number") or ""
    phone_number = str(raw_phone).strip()
    otp = str(request.data.get("otp") or request.data.get("code") or "").strip()
    
    if not otp:
        return Response({"error": "OTP is required.", "ok": False, "success": False}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ensure_blinkit_auth_key()
        headers = get_blinkit_api_headers()
        url = "https://blinkit.com/v2/accounts/verify/phone/code/"
        res = requests.post(url, data={"user_phone": phone_number, "verify_code": otp}, headers=headers, impersonate="chrome110", timeout=10)

        if res.status_code == 200:
            data = res.json()
            if data.get("verified") and data.get("access_token"):
                BLINKIT_SESSION["is_logged_in"] = True
                BLINKIT_SESSION["access_token"] = data["access_token"]
                BLINKIT_SESSION["user_id"] = data.get("user", {}).get("id")
                
                # Immediately fetch & sync real user orders
                fetch_blinkit_orders_internal(force_refresh=True)

                return Response({
                    "message": "Successfully logged in to Blinkit!",
                    "ok": True,
                    "success": True,
                    "session": BLINKIT_SESSION
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": data.get("message") or "Invalid OTP verification code.", "ok": False, "success": False}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": f"Blinkit API error (Status {res.status_code})", "ok": False, "success": False}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e), "ok": False, "success": False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def blinkit_logout(request):
    BLINKIT_SESSION["is_logged_in"] = False
    BLINKIT_SESSION["access_token"] = None
    BLINKIT_ORDER_CACHE["data"] = None
    return Response({"message": "Logged out from Blinkit."}, status=status.HTTP_200_OK)

@api_view(['GET'])
def blinkit_orders(request):
    try:
        force_refresh = request.query_params.get("refresh") == "true"
        orders_list = fetch_blinkit_orders_internal(force_refresh=force_refresh)

        output_orders = []
        for ord_item in orders_list:
            ord_id = str(ord_item.get("order_id", ""))
            existing_exp = Expense.objects.filter(description__icontains=ord_id).first()
            
            ord_copy = dict(ord_item)
            if existing_exp:
                ord_copy["is_split"] = True
                parsed_notes = None
                if existing_exp.notes:
                    try:
                        parsed_notes = json.loads(existing_exp.notes)
                    except Exception:
                        pass
                
                split_mode_val = "ITEMIZED"
                items_saved = []
                if isinstance(parsed_notes, dict):
                    split_mode_val = parsed_notes.get("split_mode", "ITEMIZED")
                    items_saved = parsed_notes.get("items", [])
                elif isinstance(parsed_notes, list):
                    items_saved = parsed_notes

                ord_copy["existing_split"] = {
                    "expense_id": existing_exp.id,
                    "split_mode": split_mode_val,
                    "notes_items": items_saved
                }
            else:
                ord_copy["is_split"] = False
                ord_copy["existing_split"] = None

            output_orders.append(ord_copy)

        return Response({"orders": output_orders, "cached": not force_refresh}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def blinkit_order_cart_details(request):
    order_id = request.data.get("order_id")
    orders_list = fetch_blinkit_orders_internal(force_refresh=False)
    target_ord = next((o for o in orders_list if str(o.get("order_id")) == str(order_id)), None)

    if not target_ord:
        return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "order_id": order_id,
        "item_details": target_ord.get("item_details", []),
        "other_charges": target_ord.get("other_charges", 0.0)
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def blinkit_split_order(request):
    try:
        res = GrocerySplitEngine.process_split(
            platform_name="Blinkit",
            group_id=request.data.get("group_id"),
            buyer_id=request.data.get("buyer_id"),
            order_id=request.data.get("order_id", "Blinkit Order"),
            total_amount=float(request.data.get("total_amount", 0.0)),
            split_mode=request.data.get("split_mode", "BILL_LEVEL"),
            item_splits_data=request.data.get("item_splits", []),
            bill_split_data=request.data.get("bill_split", {}),
            description=request.data.get("description"),
            placed_at=request.data.get("placed_at")
        )
        return Response(res, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def blinkit_remove_split(request):
    order_id = request.data.get("order_id")
    if not order_id:
        return Response({"error": "order_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    res = GrocerySplitEngine.remove_split(order_id)
    return Response(res, status=status.HTTP_200_OK)
