from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.users.views import UserProfileViewSet
from apps.groups.views import GroupViewSet
from apps.expenses.views import ExpenseViewSet, SettlementViewSet
from apps.expenses import blinkit_views
from apps.expenses import swiggy_views

router = DefaultRouter()
router.register(r'users', UserProfileViewSet, basename='user')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'settlements', SettlementViewSet, basename='settlement')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Blinkit API endpoints
    path('api/blinkit/status/', blinkit_views.blinkit_status, name='blinkit_status'),
    path('api/blinkit/send_otp/', blinkit_views.blinkit_send_otp, name='blinkit_send_otp'),
    path('api/blinkit/verify_otp/', blinkit_views.blinkit_verify_otp, name='blinkit_verify_otp'),
    path('api/blinkit/logout/', blinkit_views.blinkit_logout, name='blinkit_logout'),
    path('api/blinkit/orders/', blinkit_views.blinkit_orders, name='blinkit_orders'),
    path('api/blinkit/order_cart_details/', blinkit_views.blinkit_order_cart_details, name='blinkit_order_cart_details'),
    path('api/blinkit/split_order/', blinkit_views.blinkit_split_order, name='blinkit_split_order'),
    path('api/blinkit/remove_split/', blinkit_views.blinkit_remove_split, name='blinkit_remove_split'),

    # Swiggy Instamart API endpoints
    path('api/swiggy/status/', swiggy_views.swiggy_status, name='swiggy_status'),
    path('api/swiggy/send_otp/', swiggy_views.swiggy_send_otp, name='swiggy_send_otp'),
    path('api/swiggy/verify_otp/', swiggy_views.swiggy_verify_otp, name='swiggy_verify_otp'),
    path('api/swiggy/logout/', swiggy_views.swiggy_logout, name='swiggy_logout'),
    path('api/swiggy/auth_url/', swiggy_views.swiggy_auth_url, name='swiggy_auth_url'),
    path('api/swiggy/callback/', swiggy_views.swiggy_callback, name='swiggy_callback'),
    path('api/swiggy/orders/', swiggy_views.swiggy_orders, name='swiggy_orders'),
    path('api/swiggy/split_order/', swiggy_views.swiggy_split_order, name='swiggy_split_order'),
    path('api/swiggy/remove_split/', swiggy_views.swiggy_remove_split, name='swiggy_remove_split'),
    path('api/swiggy/sync_manual/', swiggy_views.swiggy_sync_manual, name='swiggy_sync_manual'),

    # API router
    path('api/', include((router.urls, 'api'))),
]
