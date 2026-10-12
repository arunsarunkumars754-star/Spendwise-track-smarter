"""
Django admin configuration for SpendWise models.
"""

from django.contrib import admin

from .models import Budget, Category, RecurringTransaction, Transaction, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'currency', 'phone', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'category_type', 'color', 'icon', 'created_at')
    list_filter = ('category_type', 'created_at')
    search_fields = ('name', 'user__username', 'description')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'transaction_type', 'amount', 'transaction_date', 'payment_method')
    list_filter = ('transaction_type', 'payment_method', 'transaction_date')
    search_fields = ('title', 'description', 'reference_number', 'user__username')
    date_hierarchy = 'transaction_date'
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'category', 'amount_limit', 'period', 'start_date', 'end_date')
    list_filter = ('period', 'start_date', 'end_date')
    search_fields = ('name', 'user__username')


@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'amount', 'frequency', 'next_due_date', 'is_active')
    list_filter = ('frequency', 'is_active', 'transaction_type')
    search_fields = ('title', 'user__username')
