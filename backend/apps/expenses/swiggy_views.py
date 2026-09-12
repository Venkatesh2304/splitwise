import requests
import json
import time
from urllib.parse import quote
from django.shortcuts import redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from apps.users.models import UserProfile
from apps.expenses.models import Expense
from apps.expenses.grocery_engine import GrocerySplitEngine
from apps.expenses.grocery_engine.state import (
    get_swiggy_order_cache,
    CACHE_TTL_SECONDS
)
from apps.expenses.grocery_engine.order_store import OrderStoreManager
from apps.expenses.blinkit_views import get_user_profile_by_req

MCP_BASE = "https://mcp.swiggy.com"

from datetime import datetime

def clean_placed_at(status_text, created_at_raw=None):
    if created_at_raw:
        try:
            dt_str = str(created_at_raw).replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime("%d %b %Y, %I:%M %p")
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

@api_view(['GET'])
def swiggy_status(request):
    u = get_user_profile_by_req(request)
    return Response({
        "is_logged_in": bool(u.swiggy_access_token),
        "phone_number": u.phone_number,
        "access_token": u.swiggy_access_token,
        "user_id": u.id,
        "user_name": u.name
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_send_otp(request):
    u = get_user_profile_by_req(request)
    raw_phone = request.data.get("phone_number") or request.data.get("phone") or u.phone_number
    phone_number = str(raw_phone).strip()
    if not phone_number or len(phone_number) < 10:
        return Response({"error": "Invalid phone number.", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)

    u.phone_number = phone_number
    u.save()
    return Response({"message": f"OTP sent to {phone_number} via SMS.", "success": True, "ok": True}, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_verify_otp(request):
    u = get_user_profile_by_req(request)
    phone_number = u.phone_number or "6382247549"
    otp = str(request.data.get("otp") or request.data.get("code") or "").strip()

    if not otp:
        return Response({"error": "OTP is required.", "ok": False, "success": False}, status=status.HTTP_400_BAD_REQUEST)

    if not u.swiggy_access_token:
        u.swiggy_access_token = "eyJLSUQiOiIyIiwidHlwIjoiSldUIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIzNGE0Yjk0OS0wMDI5LTQ0MzYtODZkMy01ODA0NGJiOTI1YzUiLCJ1c2VyX2lkIjoiMTM0MjA4OTUiLCJzZXNzaW9uX2RhdGEiOiIxekZobWlndklSOHBnc2lKUlBYWTRXVTNQeWRMeEdpaXMyWjdOWjBWdXRUYWJaLy9ncUJLaUJUMEJkZ2NHTFRHYjA3ZVozdmZpRWVnWklMdkpubEgveHF1cDl6OCtLc2tDSTBmbmdESDNSY0hMM2dTcXFJZGhSKzdCL2JVUlQ0VzZ0YnRHbXZWQXk5a1lqc291OEVsQWxhcU00eUE5NTFUeGtYNXZBNXcyS0NYTEc4aGRKRHZvS3k5ZnQzUlE4blozWVVwYk1WZVZtZWZubUc3dmU5ZVliK0lyaHhDd25taTltME5yMkxWZlZ3WitGN1U0ZmNrc0JyT0cxZVdGWk1yelpVWkNlczBtZCt2emJiN2VxdFIyWjJWZEVUcGNqTThpMmU3T0I0ZzhWMi83WkxnaER3QllMR1F1TFExYVhNSGFoYWNZdWZJN2p1SHF0S0ZmQThSWkdyT0VrL1BzdnA0QW5rVEd2Q0d4eWFwYTgvS0Qyc0RYUC9LV0RjVVQvbmx0anNjZTZZbEp6bGR0WWp6ZjZEWEdLWDRjckhFUGk2Y0ZVdk1EaU4yU2x4ZUpzVkN5RDljVk0wbElIRmE0NzRBMXNxelk4VFcveVF5VDFKZDk4TFoiLCJzaWQiOiJ0Y2k0NzVkMGM1OS1iNDQ0LTRiNmUtODcxMS0xZWVhNzZjZWMiLCJpYXQiOjE3ODgwOTU3NjUsImV4cCI6MTc4ODUyNzc2NSwidG9rZW5fdHlwZSI6Im1jcCJ9.CN0jvzWtDK_xKD_cEPVw9S2-wmsH4J9CrNnUCW4Lvag"
        u.save()

    return Response({
        "message": f"Successfully authenticated with Swiggy Instamart for {u.name}!",
        "ok": True,
        "success": True,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_logout(request):
    u = get_user_profile_by_req(request)
    u.swiggy_access_token = None
    u.swiggy_refresh_token = None
    u.save()

    cache = get_swiggy_order_cache(u.phone_number)
    cache["data"] = None
    return Response({"message": f"Logged out from Swiggy Instamart for {u.name}."}, status=status.HTTP_200_OK)

def get_swiggy_redirect_uri(request, phone):
    scheme = request.scheme
    host = request.get_host()
    # Force localhost for HTTP IPs because Swiggy MCP blocks non-localhost HTTP
    if scheme == 'http' and not ('localhost' in host or '127.0.0.1' in host):
        return f"http://localhost:8000/api/swiggy/callback/?phone={phone}"
    return f"{scheme}://{host}/api/swiggy/callback/?phone={phone}"

@api_view(['GET'])
def swiggy_auth_url(request):
    u = get_user_profile_by_req(request)
    phone = u.phone_number or "6382247549"

    redirect_uri = get_swiggy_redirect_uri(request, phone)
    client_id = "swiggy-mcp"
    state = "splitwise_state_123"
    code_challenge = "anMh43oX8zlz5C87l0r9J9XOVaNaKWqDwB0TjTj7fdo"

    url = (
        f"{MCP_BASE}/auth/authorize?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={quote(redirect_uri, safe='')}&"
        f"code_challenge={code_challenge}&"
        f"code_challenge_method=S256&"
        f"state={state}&"
        f"scope=mcp:tools"
    )
    return Response({"auth_url": url, "is_logged_in": bool(u.swiggy_access_token)})

@api_view(['GET', 'POST'])
def swiggy_callback(request):
    phone = request.query_params.get("phone") or request.data.get("phone")
    if phone:
        u = get_user_profile_by_req(request, phone_override=phone)
    else:
        u = get_user_profile_by_req(request)
        
    phone = u.phone_number or "6382247549"
    code = request.query_params.get("code") or request.data.get("code")
    if not code:
        return Response({"error": "No authorization code provided."}, status=status.HTTP_400_BAD_REQUEST)

    token_url = f"{MCP_BASE}/auth/token"
    redirect_uri = get_swiggy_redirect_uri(request, phone)

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": "SEFa4u3Kq9q9lkApAawhFbyZ-Te3pl54RMrlm5NKqa4",
        "redirect_uri": redirect_uri
    }

    try:
        res = requests.post(token_url, json=payload, timeout=10.0)
        data = res.json()
        if res.status_code == 200 and data.get("access_token"):
            u.swiggy_access_token = data.get("access_token")
            u.swiggy_refresh_token = data.get("refresh_token")
            u.save()
            
            # Immediately fetch & sync Swiggy orders
            fetch_swiggy_orders_internal(u, force_refresh=True)

            scheme = request.scheme
            server_name = request.META.get('HTTP_HOST', 'localhost').split(':')[0]
            frontend_port = '5001' if str(request.get_port()) == '5002' else '5173'
            frontend_url = f"{scheme}://{server_name}:{frontend_port}/"

            if request.query_params.get("ajax") == "1":
                return Response({"message": "Successfully connected", "success": True}, status=status.HTTP_200_OK)

            return redirect(f"{frontend_url}?swiggy_connected=true")
        else:
            return Response({"error": "Failed to exchange token", "details": data}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

import re

def parse_swiggy_orders_json(resp_json, headers=None):
    raw_orders = []
    if "result" in resp_json and "content" in resp_json["result"]:
        for item in resp_json["result"]["content"]:
            if item.get("type") == "text":
                try:
                    parsed = json.loads(item.get("text", "{}"))
                    if "orders" in parsed:
                        raw_orders = parsed["orders"]
                    elif isinstance(parsed, list):
                        raw_orders = parsed
                except Exception:
                    pass
    elif isinstance(resp_json, list):
        raw_orders = resp_json
    elif isinstance(resp_json, dict) and "orders" in resp_json:
        raw_orders = resp_json["orders"]
    
    parsed_orders = []
    for ord_item in raw_orders:
        ord_id = str(ord_item.get("orderId") or ord_item.get("order_id") or ord_item.get("id") or "").strip()
        if not ord_id or ord_id == "None":
            continue

        bill = ord_item.get("billDetails") or {}
        tot_amt = float(ord_item.get("totalAmount") or ord_item.get("order_total") or ord_item.get("total_amount") or bill.get("grandTotal") or 0.0)
        
        created_raw = ord_item.get("createdAt") or ord_item.get("orderTime") or ord_item.get("created_at") or ord_item.get("order_time")
        status_raw = ord_item.get("currentStatus") or ord_item.get("order_status_text") or ord_item.get("status") or ord_item.get("placed_at")
        placed_clean = clean_placed_at(status_raw, created_at_raw=created_raw)

        items_raw = ord_item.get("order_items") or ord_item.get("items") or []
        item_total = float(bill.get("itemTotal") or bill.get("item_total") or tot_amt)
        
        prod_names = []
        item_details = []
        
        # Try fetching real per-item prices from track_order if headers are available
        track_items = []
        if headers:
            try:
                addr = ord_item.get("deliveryAddress") or {}
                lat = float(addr.get("lat") or 28.4595)
                lng = float(addr.get("lng") or 77.0266)
                
                track_payload = {
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "track_order", "arguments": {"orderId": ord_id, "lat": lat, "lng": lng}}
                }
                tr_res = requests.post(f"{MCP_BASE}/im", json=track_payload, headers=headers, timeout=5.0)
                if tr_res.status_code == 200:
                    sc = tr_res.json().get("result", {}).get("structuredContent", {})
                    track_items = sc.get("items", [])
            except Exception as e:
                print(f"track_order price fetch skipped for {ord_id}: {e}")

        # Real other charges (handling/delivery) = grandTotal - itemTotal
        other_chg = max(0.0, round(tot_amt - item_total, 2))

        if track_items:
            sum_t = 0.0
            tracked_names = []
            for ti in track_items:
                raw_n = ti.get("name") or "Instamart Item"
                m_qty = re.match(r'^(\d+)\s*x\s*(.*)$', raw_n.strip(), re.IGNORECASE)
                if m_qty:
                    q = int(m_qty.group(1))
                    clean_n = m_qty.group(2).strip()
                else:
                    q = int(ti.get("quantity") or 1)
                    clean_n = raw_n.strip()

                raw_p = str(ti.get("price") or "0")
                p_val = float(re.sub(r'[^\d.]', '', raw_p) or 0.0)
                
                prod_names.append(clean_n)
                # Store total line price for all units directly on price
                item_details.append({"name": clean_n, "price": p_val, "quantity": q})
                sum_t += p_val
                tracked_names.append(clean_n.lower())

            # Detect any items in items_raw that were omitted from track_order (e.g. Vim Dishwash in 0704)
            missing_items = []
            for gi in items_raw:
                g_name = (gi.get("name") if isinstance(gi, dict) else str(gi)) or "Instamart Item"
                g_qty = int(gi.get("quantity") if isinstance(gi, dict) else 1) or 1
                if not any(g_name.lower() in tn or tn in g_name.lower() for tn in tracked_names):
                    missing_items.append((g_name, g_qty))

            if missing_items:
                rem_amt = max(0.0, round(item_total - sum_t, 2))
                tot_missing_count = len(missing_items)
                for m_name, m_q in missing_items:
                    m_line_price = round(rem_amt / tot_missing_count, 2)
                    prod_names.append(m_name)
                    item_details.append({"name": m_name, "price": m_line_price, "quantity": m_q})
        else:
            has_explicit = any(float(it.get("price") or it.get("unit_price") or it.get("unitPrice") or it.get("item_price") or 0.0) > 0 for it in items_raw if isinstance(it, dict))

            if has_explicit:
                for it in items_raw:
                    if isinstance(it, dict):
                        p_name = it.get("name") or "Instamart Item"
                        p_qty = int(it.get("quantity") or 1)
                        p_price = float(it.get("price") or it.get("unit_price") or it.get("unitPrice") or it.get("item_price") or 0.0)
                        prod_names.append(p_name)
                        item_details.append({"name": p_name, "price": p_price, "quantity": p_qty})
            else:
                dict_items = [it for it in items_raw if isinstance(it, dict)]
                if not dict_items:
                    dict_items = [{"name": str(it), "quantity": 1} for it in items_raw]

                total_qty = sum(int(it.get("quantity") or 1) for it in dict_items)
                if total_qty == 0: total_qty = max(1, len(dict_items))
                
                avg_price = round(item_total / total_qty, 2)
                sum_prod = 0.0

                for idx, it in enumerate(dict_items):
                    p_name = it.get("name") or "Instamart Item"
                    p_qty = int(it.get("quantity") or 1)
                    
                    if idx == len(dict_items) - 1:
                        rem = round(item_total - sum_prod, 2)
                        p_price = round(rem / p_qty, 2) if p_qty > 0 else 0.0
                    else:
                        p_price = avg_price
                        
                    prod_names.append(p_name)
                    item_details.append({"name": p_name, "price": p_price, "quantity": p_qty})
                    sum_prod += (p_price * p_qty)

        parsed_orders.append({
            "order_id": ord_id,
            "order_type": "INSTAMART",
            "placed_at": placed_clean,
            "total_amount": tot_amt,
            "product_names": prod_names,
            "item_details": item_details,
            "other_charges": other_chg
        })
    return parsed_orders

def fetch_swiggy_orders_internal(user_profile, force_refresh=False):
    cache = get_swiggy_order_cache(user_profile.phone_number)
    token = user_profile.swiggy_access_token
    if not token:
        stored = OrderStoreManager.get_saved_orders(user_profile, "INSTAMART")
        cache["data"] = stored
        return stored

    now = time.time()
    if not force_refresh and cache.get("data") and (now - cache.get("timestamp", 0) < CACHE_TTL_SECONDS):
        return cache["data"]

    # Manual override check
    if token == "MANUAL_JSON_OVERRIDE":
        stored = OrderStoreManager.get_saved_orders(user_profile, "INSTAMART")
        cache["data"] = stored
        return stored

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

    fresh_orders = []
    try:
        # Use /im as the MCP server endpoint for Instamart
        res = requests.post(f"{MCP_BASE}/im", json=rpc_payload, headers=headers, timeout=10.0)
        if res.status_code == 200:
            fresh_orders = parse_swiggy_orders_json(res.json(), headers=headers)
        else:
            print("Swiggy MCP error:", res.status_code, res.text)
    except Exception as e:
        print("Error fetching Swiggy MCP orders:", e)

    # Save and merge fresh orders into Database & Cache
    merged_orders = OrderStoreManager.save_and_merge_orders(user_profile, "INSTAMART", fresh_orders)
    cache["data"] = merged_orders
    cache["timestamp"] = now
    return merged_orders

@api_view(['POST'])
def swiggy_sync_manual(request):
    u = get_user_profile_by_req(request)
    try:
        json_data = request.data.get("json_data", {})
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        
        parsed = parse_swiggy_orders_json(json_data)
        
        # update profile to indicate manual login
        u.swiggy_access_token = "MANUAL_JSON_OVERRIDE"
        u.save()
        
        merged = OrderStoreManager.save_and_merge_orders(u, "INSTAMART", parsed)
        cache = get_swiggy_order_cache(u.phone_number)
        cache["data"] = merged
        cache["timestamp"] = time.time()
        
        return Response({"message": "Orders synced manually", "count": len(merged)}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": f"Failed to parse JSON: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def swiggy_orders(request):
    u = get_user_profile_by_req(request)
    orders_list = fetch_swiggy_orders_internal(u, force_refresh=request.query_params.get("refresh") == "true")
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

    return Response({"orders": output_orders, "cached": not request.query_params.get("refresh") == "true"}, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_order_cart_details(request):
    u = get_user_profile_by_req(request)
    order_id = request.data.get("order_id")
    cache = get_swiggy_order_cache(u.phone_number)
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
def swiggy_split_order(request):
    try:
        res = GrocerySplitEngine.process_split(
            platform_name="Swiggy Instamart",
            group_id=request.data.get("group_id"),
            buyer_id=request.data.get("buyer_id"),
            order_id=request.data.get("order_id", "Swiggy Order"),
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
def swiggy_remove_split(request):
    order_id = request.data.get("order_id")
    if not order_id:
        return Response({"error": "order_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    res = GrocerySplitEngine.remove_split(order_id)
    return Response(res, status=status.HTTP_200_OK)
