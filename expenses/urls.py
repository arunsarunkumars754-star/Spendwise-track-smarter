"""
Web URL Configuration for SpendWise application.
"""

from django.urls import path
from .views import (
    landing_view,
    demo_login_view,
    register_view,
    login_view,
    logout_view,
    profile_view,
    dashboard_view,
    transaction_list_view,
    transaction_create_view,
    transaction_update_view,
    transaction_delete_view,
    category_list_view,
    category_create_view,
    category_update_view,
    category_delete_view,
    budget_list_view,
    budget_create_view,
    budget_update_view,
    budget_delete_view,
    analytics_view,
    reports_view,
    export_csv_view,
)

urlpatterns = [
    # Public Showcase & Landing
    path('', landing_view, name='landing'),
    path('landing/', landing_view, name='marketing-landing'),
    path('demo-login/', demo_login_view, name='demo-login'),

    # Authenticated Dashboard
    path('dashboard/', dashboard_view, name='dashboard'),

    # Authentication
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),

    # Transactions CRUD
    path('transactions/', transaction_list_view, name='transaction-list'),
    path('transactions/add/', transaction_create_view, name='transaction-create'),
    path('transactions/<int:pk>/edit/', transaction_update_view, name='transaction-update'),
    path('transactions/<int:pk>/delete/', transaction_delete_view, name='transaction-delete'),

    # Categories CRUD
    path('categories/', category_list_view, name='category-list'),
    path('categories/add/', category_create_view, name='category-create'),
    path('categories/<int:pk>/edit/', category_update_view, name='category-update'),
    path('categories/<int:pk>/delete/', category_delete_view, name='category-delete'),

    # Budgets CRUD
    path('budgets/', budget_list_view, name='budget-list'),
    path('budgets/add/', budget_create_view, name='budget-create'),
    path('budgets/<int:pk>/edit/', budget_update_view, name='budget-update'),
    path('budgets/<int:pk>/delete/', budget_delete_view, name='budget-delete'),

    # Analytics & Reports
    path('analytics/', analytics_view, name='analytics'),
    path('reports/', reports_view, name='reports'),
    path('reports/export-csv/', export_csv_view, name='export-csv'),
]
