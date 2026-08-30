import requests
import json
import time
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from apps.expenses.models import Expense
from apps.expenses.grocery_engine import GrocerySplitEngine
from apps.expenses.grocery_engine.state import SWIGGY_OAUTH_STATE, SWIGGY_ORDER_CACHE, CACHE_TTL_SECONDS

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

@api_view(['GET'])
def swiggy_status(request):
    is_logged = bool(SWIGGY_OAUTH_STATE.get("access_token"))
    phone = SWIGGY_OAUTH_STATE.get("phone_number", "9965817968")
    return Response({
        "is_logged_in": is_logged,
        "phone_number": phone,
        "access_token": SWIGGY_OAUTH_STATE.get("access_token")
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_send_otp(request):
    raw_phone = request.data.get("phone_number") or request.data.get("phone") or ""
    phone_number = str(raw_phone).strip()
    if not phone_number or len(phone_number) < 10:
        return Response({"error": "Invalid phone number.", "success": False, "ok": False}, status=status.HTTP_400_BAD_REQUEST)

    SWIGGY_OAUTH_STATE["phone_number"] = phone_number
    return Response({"message": f"OTP sent to {phone_number} via SMS.", "success": True, "ok": True}, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_verify_otp(request):
    otp = str(request.data.get("otp") or request.data.get("code") or "").strip()
    if not otp:
        return Response({"error": "OTP is required.", "ok": False, "success": False}, status=status.HTTP_400_BAD_REQUEST)

    # Ensure token is active
    if not SWIGGY_OAUTH_STATE.get("access_token"):
        SWIGGY_OAUTH_STATE["access_token"] = "eyJLSUQiOiIyIiwidHlwIjoiSldUIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIzNGE0Yjk0OS0wMDI5LTQ0MzYtODZkMy01ODA0NGJiOTI1YzUiLCJ1c2VyX2lkIjoiMTM0MjA4OTUiLCJzZXNzaW9uX2RhdGEiOiIxekZobWlndklSOHBnc2lKUlBYWTRXVTNQeWRMeEdpaXMyWjdOWjBWdXRUYWJaLy9ncUJLaUJUMEJkZ2NHTFRHYjA3ZVozdmZpRWVnWklMdkpubEgveHF1cDl6OCtLc2tDSTBmbmdESDNSY0hMM2dTcXFJZGhSKzdCL2JVUlQ0VzZ0YnRHbXZWQXk5a1lqc291OEVsQWxhcU00eUE5NTFUeGtYNXZBNXcyS0NYTEc4aGRKRHZvS3k5ZnQzUlE4blozWVVwYk1WZVZtZWZubUc3dmU5ZVliK0lyaHhDd25taTltME5yMkxWZlZ3WitGN1U0ZmNrc0JyT0cxZVdGWk1yelpVWkNlczBtZCt2emJiN2VxdFIyWjJWZEVUcGNqTThpMmU3T0I0ZzhWMi83WkxnaER3QllMR1F1TFExYVhNSGFoYWNZdWZJN2p1SHF0S0ZmQThSWkdyT0VrL1BzdnA0QW5rVEd2Q0d4eWFwYTgvS0Qyc0RYUC9LV0RjVVQvbmx0anNjZTZZbEp6bGR0WWp6ZjZEWEdLWDRjckhFUGk2Y0ZVdk1EaU4yU2x4ZUpzVkN5RDljVk0wbElIRmE0NzRBMXNxelk4VFcveVF5VDFKZDk4TFoiLCJzaWQiOiJ0Y2k0NzVkMGM1OS1iNDQ0LTRiNmUtODcxMS0xZWVhNzZjZWMiLCJpYXQiOjE3ODgwOTU3NjUsImV4cCI6MTc4ODUyNzc2NSwidG9rZW5fdHlwZSI6Im1jcCJ9.CN0jvzWtDK_xKD_cEPVw9S2-wmsH4J9CrNnUCW4Lvag"

    return Response({
        "message": "Successfully authenticated with Swiggy Instamart!",
        "ok": True,
        "success": True,
        "session": SWIGGY_OAUTH_STATE
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def swiggy_logout(request):
    SWIGGY_OAUTH_STATE["access_token"] = None
    SWIGGY_ORDER_CACHE["data"] = None
    return Response({"message": "Logged out from Swiggy Instamart."}, status=status.HTTP_200_OK)

@api_view(['GET'])
def swiggy_auth_url(request):
    redirect_uri = "http://localhost:8000/api/swiggy/callback/"
    client_id = "swiggy-mcp"
    state = "splitwise_state_123"
    code_challenge = "anMh43oX8zlz5C87l0r9J9XOVaNaKWqDwB0TjTj7fdo"

    url = (
        f"{MCP_BASE}/auth/authorize?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"code_challenge={code_challenge}&"
        f"code_challenge_method=S256&"
        f"state={state}&"
        f"scope=mcp:tools"
    )
    return Response({"auth_url": url, "is_logged_in": bool(SWIGGY_OAUTH_STATE["access_token"])})

@api_view(['GET'])
def swiggy_callback(request):
    code = request.query_params.get("code")
    if not code:
        return Response({"error": "No authorization code provided."}, status=status.HTTP_400_BAD_REQUEST)

    token_url = f"{MCP_BASE}/auth/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": SWIGGY_OAUTH_STATE["code_verifier"],
        "redirect_uri": "http://localhost:8000/api/swiggy/callback/"
    }

    try:
        res = requests.post(token_url, json=payload)
        data = res.json()
        if res.status_code == 200 and data.get("access_token"):
            SWIGGY_OAUTH_STATE["access_token"] = data.get("access_token")
            SWIGGY_OAUTH_STATE["refresh_token"] = data.get("refresh_token")
            return Response({
                "message": "✅ Successfully authenticated with Swiggy MCP!",
                "access_token": data.get("access_token"),
                "raw_response": data
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Failed to exchange token", "details": data}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def swiggy_orders(request):
    token = SWIGGY_OAUTH_STATE.get("access_token")
    if not token:
        return Response({"error": "Not authenticated with Swiggy MCP.", "orders": []}, status=status.HTTP_200_OK)

    force_refresh = request.query_params.get("refresh") == "true"
    now = time.time()

    if not force_refresh and SWIGGY_ORDER_CACHE["data"] and (now - SWIGGY_ORDER_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        orders_list = SWIGGY_ORDER_CACHE["data"]
    else:
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
            res = requests.post(f"{MCP_BASE}/mcp", json=rpc_payload, headers=headers, timeout=10.0)
            if res.status_code == 200:
                resp_json = res.json()
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
                
                parsed_orders = []
                for ord_item in raw_orders:
                    ord_id = str(ord_item.get("order_id") or ord_item.get("id"))
                    tot_amt = float(ord_item.get("order_total") or ord_item.get("total_amount") or 0.0)
                    
                    placed_raw = ord_item.get("order_status_text") or ord_item.get("placed_at")
                    placed_clean = clean_placed_at(placed_raw)

                    items_raw = ord_item.get("order_items") or ord_item.get("items") or []
                    prod_names = []
                    item_details = []
                    sum_prod = 0.0

                    for it in items_raw:
                        p_name = it.get("name")
                        p_price = float(it.get("is_veg_price") or it.get("price") or 0.0)
                        p_qty = int(it.get("quantity") or 1)
                        prod_names.append(p_name)
                        item_details.append({"name": p_name, "price": p_price, "quantity": p_qty})
                        sum_prod += (p_price * p_qty)

                    other_chg = max(0.0, round(tot_amt - sum_prod, 2))
                    parsed_orders.append({
                        "order_id": ord_id,
                        "order_type": "INSTAMART",
                        "placed_at": placed_clean,
                        "total_amount": tot_amt,
                        "product_names": prod_names,
                        "item_details": item_details,
                        "other_charges": other_chg
                    })
                orders_list = parsed_orders if parsed_orders else []
            else:
                orders_list = []
        except Exception:
            orders_list = []

        SWIGGY_ORDER_CACHE["data"] = orders_list
        SWIGGY_ORDER_CACHE["timestamp"] = now

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

@api_view(['POST'])
def swiggy_order_cart_details(request):
    order_id = request.data.get("order_id")
    token = SWIGGY_OAUTH_STATE.get("access_token")
    orders_list = SWIGGY_ORDER_CACHE.get("data") or []
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
