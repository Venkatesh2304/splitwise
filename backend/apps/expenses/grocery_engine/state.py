import time
import uuid

# Per-phone isolated Blinkit session storage
BLINKIT_SESSIONS = {
    "6382247549": {
        "phone_number": "6382247549",
        "access_token": "v2::41bccbe5-8c91-430f-8ed0-04decc5924eb",
        "auth_key": "c761ec3633c22afad934fb17a66385c1c06c5472b4898b866b7306186d0bb477",
        "device_id": "5f2a83a6911b4f8b",
        "session_uuid": "d1e49859-cb40-4f0a-8110-c213f22a718a",
        "is_logged_in": True
    },
    "9965817968": {
        "phone_number": "9965817968",
        "access_token": "v2::89a1cce4-9b22-4411-9ff1-12cdeaa558ab",
        "auth_key": "c761ec3633c22afad934fb17a66385c1c06c5472b4898b866b7306186d0bb477",
        "device_id": "8a3b91c742019e1f",
        "session_uuid": "e2f58912-ab50-4d1b-9221-d324911b829b",
        "is_logged_in": True
    }
}

BLINKIT_ORDER_CACHES = {}

def get_blinkit_session(phone_number=None):
    phone_clean = str(phone_number or "6382247549").strip()
    if phone_clean not in BLINKIT_SESSIONS:
        BLINKIT_SESSIONS[phone_clean] = {
            "phone_number": phone_clean,
            "access_token": None,
            "auth_key": None,
            "device_id": uuid.uuid4().hex[:16],
            "session_uuid": str(uuid.uuid4()),
            "is_logged_in": False
        }
    return BLINKIT_SESSIONS[phone_clean]

def get_blinkit_order_cache(phone_number=None):
    phone_clean = str(phone_number or "6382247549").strip()
    if phone_clean not in BLINKIT_ORDER_CACHES:
        BLINKIT_ORDER_CACHES[phone_clean] = {
            "timestamp": 0,
            "data": None
        }
    return BLINKIT_ORDER_CACHES[phone_clean]

# Swiggy per-phone session & cache storage
SWIGGY_SESSIONS = {
    "6382247549": {
        "phone_number": "6382247549",
        "code_verifier": "SEFa4u3Kq9q9lkApAawhFbyZ-Te3pl54RMrlm5NKqa4",
        "access_token": "eyJLSUQiOiIyIiwidHlwIjoiSldUIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIzNGE0Yjk0OS0wMDI5LTQ0MzYtODZkMy01ODA0NGJiOTI1YzUiLCJ1c2VyX2lkIjoiMTM0MjA4OTUiLCJzZXNzaW9uX2RhdGEiOiIxekZobWlndklSOHBnc2lKUlBYWTRXVTNQeWRMeEdpaXMyWjdOWjBWdXRUYWJaLy9ncUJLaUJUMEJkZ2NHTFRHYjA3ZVozdmZpRWVnWklMdkpubEgveHF1cDl6OCtLc2tDSTBmbmdESDNSY0hMM2dTcXFJZGhSKzdCL2JVUlQ0VzZ0YnRHbXZWQXk5a1lqc291OEVsQWxhcU00eUE5NTFUeGtYNXZBNXcyS0NYTEc4aGRKRHZvS3k5ZnQzUlE4blozWVVwYk1WZVZtZWZubUc3dmU5ZVliK0lyaHhDd25taTltME5yMkxWZlZ3WitGN1U0ZmNrc0JyT0cxZVdGWk1yelpVWkNlczBtZCt2emJiN2VxdFIyWjJWZEVUcGNqTThpMmU3T0I0ZzhWMi83WkxnaER3QllMR1F1TFExYVhNSGFoYWNZdWZJN2p1SHF0S0ZmQThSWkdyT0VrL1BzdnA0QW5rVEd2Q0d4eWFwYTgvS0Qyc0RYUC9LV0RjVVQvbmx0anNjZTZZbEp6bGR0WWp6ZjZEWEdLWDRjckhFUGk2Y0ZVdk1EaU4yU2x4ZUpzVkN5RDljVk0wbElIRmE0NzRBMXNxelk4VFcveVF5VDFKZDk4TFoiLCJzaWQiOiJ0Y2k0NzVkMGM1OS1iNDQ0LTRiNmUtODcxMS0xZWVhNzZjZWMiLCJpYXQiOjE3ODgwOTU3NjUsImV4cCI6MTc4ODUyNzc2NSwidG9rZW5fdHlwZSI6Im1jcCJ9.CN0jvzWtDK_xKD_cEPVw9S2-wmsH4J9CrNnUCW4Lvag",
        "refresh_token": None
    },
    "9965817968": {
        "phone_number": "9965817968",
        "code_verifier": "SEFa4u3Kq9q9lkApAawhFbyZ-Te3pl54RMrlm5NKqa4",
        "access_token": "eyJLSUQiOiIyIiwidHlwIjoiSldUIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIzNGE0Yjk0OS0wMDI5LTQ0MzYtODZkMy01ODA0NGJiOTI1YzUiLCJ1c2VyX2lkIjoiMTM0MjA4OTUiLCJzZXNzaW9uX2RhdGEiOiIxekZobWlndklSOHBnc2lKUlBYWTRXVTNQeWRMeEdpaXMyWjdOWjBWdXRUYWJaLy9ncUJLaUJUMEJkZ2NHTFRHYjA3ZVozdmZpRWVnWklMdkpubEgveHF1cDl6OCtLc2tDSTBmbmdESDNSY0hMM2dTcXFJZGhSKzdCL2JVUlQ0VzZ0YnRHbXZWQXk5a1lqc291OEVsQWxhcU00eUE5NTFUeGtYNXZBNXcyS0NYTEc4aGRKRHZvS3k5ZnQzUlE4blozWVVwYk1WZVZtZWZubUc3dmU5ZVliK0lyaHhDd25taTltME5yMkxWZlZ3WitGN1U0ZmNrc0JyT0cxZVdGWk1yelpVWkNlczBtZCt2emJiN2VxdFIyWjJWZEVUcGNqTThpMmU3T0I0ZzhWMi83WkxnaER3QllMR1F1TFExYVhNSGFoYWNZdWZJN2p1SHF0S0ZmQThSWkdyT0VrL1BzdnA0QW5rVEd2Q0d4eWFwYTgvS0Qyc0RYUC9LV0RjVVQvbmx0anNjZTZZbEp6bGR0WWp6ZjZEWEdLWDRjckhFUGk2Y0ZVdk1EaU4yU2x4ZUpzVkN5RDljVk0wbElIRmE0NzRBMXNxelk4VFcveVF5VDFKZDk4TFoiLCJzaWQiOiJ0Y2k0NzVkMGM1OS1iNDQ0LTRiNmUtODcxMS0xZWVhNzZjZWMiLCJpYXQiOjE3ODgwOTU3NjUsImV4cCI6MTc4ODUyNzc2NSwidG9rZW5fdHlwZSI6Im1jcCJ9.CN0jvzWtDK_xKD_cEPVw9S2-wmsH4J9CrNnUCW4Lvag",
        "refresh_token": None
    }
}

SWIGGY_OAUTH_STATE = SWIGGY_SESSIONS["6382247549"]
SWIGGY_ORDER_CACHES = {}

def get_swiggy_session(phone_number=None):
    phone_clean = str(phone_number or "6382247549").strip()
    if phone_clean not in SWIGGY_SESSIONS:
        SWIGGY_SESSIONS[phone_clean] = {
            "phone_number": phone_clean,
            "code_verifier": "SEFa4u3Kq9q9lkApAawhFbyZ-Te3pl54RMrlm5NKqa4",
            "access_token": None,
            "refresh_token": None
        }
    return SWIGGY_SESSIONS[phone_clean]

def get_swiggy_order_cache(phone_number=None):
    phone_clean = str(phone_number or "6382247549").strip()
    if phone_clean not in SWIGGY_ORDER_CACHES:
        SWIGGY_ORDER_CACHES[phone_clean] = {
            "timestamp": 0,
            "data": None
        }
    return SWIGGY_ORDER_CACHES[phone_clean]

CACHE_TTL_SECONDS = 600
