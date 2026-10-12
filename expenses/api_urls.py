"""
API URL Routing for SpendWise /api/v1/ endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    AnalyticsAPIView,
    BudgetViewSet,
    CategoryViewSet,
    CustomAuthToken,
    DashboardSummaryAPIView,
    ExportTransactionsAPIView,
    TransactionViewSet,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='api-category')
router.register(r'transactions', TransactionViewSet, basename='api-transaction')
router.register(r'budgets', BudgetViewSet, basename='api-budget')

urlpatterns = [
    # Auth Token
    path('auth/token/', CustomAuthToken.as_view(), name='api-token-auth'),
    
    # ViewSets (CRUD)
    path('', include(router.urls)),
    
    # Aggregated Analytics & Reports
    path('dashboard/summary/', DashboardSummaryAPIView.as_view(), name='api-dashboard-summary'),
    path('analytics/', AnalyticsAPIView.as_view(), name='api-analytics'),
    path('reports/export/', ExportTransactionsAPIView.as_view(), name='api-reports-export'),
]
