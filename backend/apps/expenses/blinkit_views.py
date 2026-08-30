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
from apps.expenses.grocery_engine.state import (
    get_blinkit_session,
    get_blinkit_order_cache,
    CACHE_TTL_SECONDS
)

REQ_KEY = "c0e6868e-1180-400c-be51-f473479f1f0a"

def get_user_profile_by_req(request, phone_override=None):
    if phone_override:
        u = UserProfile.objects.filter(phone_number=str(phone_override).strip()).first()
        if u: return u

    user_id = request.headers.get("X-User-Id") or request.query_params.get("user_id") or request.data.get("user_id")
    if user_id:
        u = UserProfile.objects.filter(id=user_id).first()
        if u: return u

    phone = request.headers.get("X-Phone-Number") or request.query_params.get("phone") or request.query_params.get("phone_number") or request.data.get("phone") or request.data.get("phone_number")
    if phone:
        u = UserProfile.objects.filter(phone_number=str(phone).strip()).first()
        if u: return u

    return UserProfile.objects.filter(username="venkatesh").first()

def get_blinkit_api_headers(user_profile, include_auth_key=True):
    if not user_profile.blinkit_device_id:
        user_profile.blinkit_device_id = uuid.uuid4().hex[:16]
        user_profile.save()
    if not user_profile.blinkit_session_uuid:
        user_profile.blinkit_session_uuid = str(uuid.uuid4())
        user_profile.save()

    headers = {
        "app_client": "consumer_web",
        "platform": "desktop_web",
        "web_app_version": "1008010016",
        "rn_bundle_version": "1009003012",
        "app_version": "52434332",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "req_key": REQ_KEY,
        "device_id": user_profile.blinkit_device_id,
        "session_uuid": user_profile.blinkit_session_uuid,
        "referer": "https://blinkit.com/",
        "origin": "https://blinkit.com"
    }

    if include_auth_key and user_profile.blinkit_auth_key:
        headers["auth_key"] = user_profile.blinkit_auth_key

    if user_profile.blinkit_access_token:
        headers["access_token"] = user_profile.blinkit_access_token

    return headers

def ensure_blinkit_auth_key(user_profile):
    if user_profile.blinkit_auth_key:
        return user_profile.blinkit_auth_key

    try:
        headers = get_blinkit_api_headers(user_profile, include_auth_key=False)
        url = "https://blinkit.com/v2/accounts/auth_key/"
        res = requests.get(url, headers=headers, impersonate="chrome110", timeout=10)
        if res.status_code == 200:
            data = res.json()
            auth_key = data.get("auth_key")
            if auth_key:
                user_profile.blinkit_auth_key = auth_key
                user_profile.save()
                return auth_key
    except Exception as e:
        print(f"Error getting Blinkit auth key for user {user_profile.name}: {e}")
    return None

def extract_blinkit_orders_from_sdui(root):
    orders = []
    if not isinstance(root, (dict, list)):
        return orders

    def visit(node):
        if isinstance(node, list):
            for item in node: visit(item)
            return
        if not isinstance(node, dict):
            return

        w_type = str(node.get("widget_type") or node.get("type") or node.get("id") or "")
        data_obj = node.get("data") or {}

        if ("order" in w_type.lower() or "order_card" in str(data_obj).lower()) and isinstance(data_obj, dict):
            ord_id_raw = data_obj.get("order_id") or data_obj.get("id") or node.get("order_id")
            if not ord_id_raw:
                t_val = str(data_obj.get("title") or data_obj.get("header") or "")
                m = re.search(r'CRN[-\s]?(\d+)', t_val, re.IGNORECASE)
                if m: ord_id_raw = m.group(1)

            if ord_id_raw:
                order_id = str(ord_id_raw).strip()
                placed_at = data_obj.get("placed_at") or data_obj.get("subtitle") or data_obj.get("status_text") or "Recently"
                total = float(data_obj.get("total_amount") or data_obj.get("amount") or data_obj.get("price") or 0.0)

                items_raw = data_obj.get("items") or data_obj.get("order_items") or []
                prod_names = []
                exact_items = []

                if isinstance(items_raw, list):
                    for it in items_raw:
                        if isinstance(it, dict):
                            pname = it.get("name") or it.get("title") or "Grocery Item"
                            pprice = float(it.get("price") or it.get("unit_price") or 0.0)
                            pqty = int(it.get("quantity") or it.get("qty") or 1)
                            prod_names.append(pname)
                            exact_items.append({"name": pname, "price": pprice, "quantity": pqty})
                        elif isinstance(it, str):
                            prod_names.append(it)
                            exact_items.append({"name": it, "price": 0.0, "quantity": 1})

                other_chg = 0.0
                if not exact_items and prod_names:
                    approx_price = round(total / len(prod_names), 2) if len(prod_names) > 0 else 0.0
                    exact_items = [{"name": pname, "price": approx_price, "quantity": 1} for pname in prod_names]
                elif exact_items:
                    sum_items = sum(it["price"] * it["quantity"] for it in exact_items)
                    other_chg = max(0.0, round(total - sum_items, 2))

                if order_id and not any(o['order_id'] == order_id for o in orders):
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

def fetch_blinkit_orders_internal(user_profile, force_refresh=False):
    cache = get_blinkit_order_cache(user_profile.phone_number)
    now = time.time()

    if not force_refresh and cache.get("data") and (now - cache.get("timestamp", 0) < CACHE_TTL_SECONDS):
        return cache["data"]

    access_token = user_profile.blinkit_access_token
    if not access_token:
        orders_list = []
    else:
        try:
            ensure_blinkit_auth_key(user_profile)
            headers = get_blinkit_api_headers(user_profile)
            url = "https://blinkit.com/v1/layout/order_history"
            res = requests.post(url, headers=headers, json={}, impersonate="chrome110", timeout=10)
            if res.status_code == 200:
                parsed_orders = extract_blinkit_orders_from_sdui(res.json())
                orders_list = parsed_orders
            else:
                orders_list = []
        except Exception as e:
            print(f"Error fetching Blinkit orders for {user_profile.name}: {e}")
            orders_list = []

    cache["data"] = orders_list
    cache["timestamp"] = now
    return orders_list

@api_view(['GET'])
def blinkit_status(request):
    u = get_user_profile_by_req(request)
    return Response({
        "phone_number": u.phone_number,
        "is_logged_in": bool(u.blinkit_access_token),
        "access_token": u.blinkit_access_token,
        "user_id": u.id,
        "user_name": u.name
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def blinkit_send_otp(request):
    u = get_user_profile_by_req(request)
    raw_phone = request.data.get("phone_number") or request.data.get("phone") or u.phone_number
    phone_number = str(raw_phone).strip()

    if not phone_number or len(phone_number) < 10:
        return Response({"error": "Invalid 10-digit mobile number.", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)

    u.phone_number = phone_number
    u.save()

    try:
        ensure_blinkit_auth_key(u)
        headers = get_blinkit_api_headers(u)
        url = "https://blinkit.com/v2/accounts/"
        res = requests.post(url, data={"user_phone": phone_number}, headers=headers, impersonate="chrome110", timeout=10)

        if res.status_code == 200:
            data = res.json()
            if data.get("sms_sent") or data.get("success") or data.get("login"):
                return Response({"message": data.get("message") or f"OTP sent to {phone_number} via SMS.", "success": True, "ok": True}, status=status.HTTP_200_OK)
            else:
                return Response({"error": data.get("message") or "Failed to send OTP.", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": f"Blinkit API error (Status {res.status_code})", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e), "success": False, "ok": False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def blinkit_verify_otp(request):
    u = get_user_profile_by_req(request)
    phone_number = u.phone_number or "6382247549"
    otp = str(request.data.get("otp") or request.data.get("code") or "").strip()
    
    if not otp:
        return Response({"error": "OTP is required.", "ok": False, "success": False}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ensure_blinkit_auth_key(u)
        headers = get_blinkit_api_headers(u)
        url = "https://blinkit.com/v2/accounts/verify/phone/code/"
        res = requests.post(url, data={"user_phone": phone_number, "verify_code": otp}, headers=headers, impersonate="chrome110", timeout=10)

        if res.status_code == 200:
            data = res.json()
            token = data.get("access_token") or data.get("token") or (data.get("data") or {}).get("access_token")
            if token or data.get("verified") or data.get("success") or data.get("login"):
                u.blinkit_access_token = token or "SESSION_ACTIVE"
                u.save()
                
                # Immediately fetch & sync real user orders
                fetch_blinkit_orders_internal(u, force_refresh=True)

                return Response({
                    "message": f"Successfully logged in to Blinkit for {u.name}!",
                    "ok": True,
                    "success": True,
                    "phone_number": u.phone_number
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": data.get("message") or "Invalid OTP verification code.", "ok": False, "success": False}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": f"Blinkit API error (Status {res.status_code})", "ok": False, "success": False}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e), "ok": False, "success": False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def blinkit_logout(request):
    u = get_user_profile_by_req(request)
    u.blinkit_access_token = None
    u.save()

    cache = get_blinkit_order_cache(u.phone_number)
    cache["data"] = None
    return Response({"message": f"Logged out from Blinkit for {u.name}."}, status=status.HTTP_200_OK)

@api_view(['GET'])
def blinkit_orders(request):
    try:
        u = get_user_profile_by_req(request)
        force_refresh = request.query_params.get("refresh") == "true"
        orders_list = fetch_blinkit_orders_internal(u, force_refresh=force_refresh)

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
        return Response({"error": str(e), "orders": []}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def blinkit_order_cart_details(request):
    u = get_user_profile_by_req(request)
    order_id = request.data.get("order_id")
    cache = get_blinkit_order_cache(u.phone_number)
    orders_list = cache.get("data") or []
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
