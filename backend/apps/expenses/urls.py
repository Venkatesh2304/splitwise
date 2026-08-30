from rest_framework.routers import DefaultRouter
from .views import ExpenseViewSet, SettlementViewSet

router = DefaultRouter()
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'settlements', SettlementViewSet, basename='settlement')

urlpatterns = router.urls
