"""
Django Web Views for SpendWise Application.
Implements authentication, dashboard, transactions, categories, budgets, analytics, and reports.
"""

from decimal import Decimal
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q

from .models import Category, Transaction, Budget, UserProfile, create_default_categories_for_user
from .forms import (
    UserRegistrationForm,
    UserProfileForm,
    CategoryForm,
    TransactionForm,
    BudgetForm
)
from .services import FinanceService


# ==============================================================================
# Public Showcase & Landing Views
# ==============================================================================

def landing_view(request):
    """
    Public SaaS marketing and showcase landing page for SpendWise.
    Provides feature highlights, interactive savings calculator, live preview cards,
    transparent pricing, FAQ, and 1-click Demo Sandbox access.
    """
    if request.user.is_authenticated and request.GET.get('view') != 'showcase':
        return redirect('dashboard')

    total_tx_count = Transaction.objects.count()
    total_categories = Category.objects.count()
    total_budgets = Budget.objects.count()

    context = {
        'is_landing': True,
        'total_tx_count': max(total_tx_count, 3500),
        'total_categories': total_categories,
        'total_budgets': total_budgets,
    }
    return render(request, 'landing.html', context)


def demo_login_view(request):
    """
    Instant 1-Click login into pre-configured Demo Account.
    Provides immediate access to the full live interactive dashboard with sample data.
    """
    demo_user = User.objects.filter(username='demo').first()
    if not demo_user:
        demo_user = User.objects.create_user(
            username='demo',
            email='demo@spendwise.local',
            password='demo1234',
            first_name='Demo',
            last_name='User'
        )
        create_default_categories_for_user(demo_user)
    
    login(request, demo_user)
    messages.success(
        request,
        "⚡ Welcome to the SpendWise Live Sandbox! You are logged in as the Demo User. "
        "Explore real-time analytics, add transactions, track budgets, and inspect financial reports."
    )
    return redirect('dashboard')


# ==============================================================================
# Authentication Views
# ==============================================================================

def register_view(request):
    """User account registration view."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to SpendWise, {user.first_name or user.username}! Default categories have been initialized for you.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors below to register.")
    else:
        form = UserRegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'dashboard')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = AuthenticationForm()

    return render(request, 'registration/login.html', {'form': form})


@login_required
def logout_view(request):
    """Logs out the user and redirects to login."""
    logout(request)
    messages.info(request, "You have been logged out safely.")
    return redirect('login')


@login_required
def profile_view(request):
    """User profile editing and password change view."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
            pwd_form = PasswordChangeForm(request.user)
            if form.is_valid():
                form.save()
                messages.success(request, "Your profile details have been updated successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Failed to update profile. Please verify your inputs.")

        elif action == 'change_password':
            form = UserProfileForm(instance=profile, user=request.user)
            pwd_form = PasswordChangeForm(request.user, request.POST)
            if pwd_form.is_valid():
                user = pwd_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password was changed successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Password change failed. Please review the errors.")
        else:
            form = UserProfileForm(instance=profile, user=request.user)
            pwd_form = PasswordChangeForm(request.user)
    else:
        form = UserProfileForm(instance=profile, user=request.user)
        pwd_form = PasswordChangeForm(request.user)

    return render(request, 'expenses/profile.html', {
        'form': form,
        'pwd_form': pwd_form,
        'profile': profile,
    })


# ==============================================================================
# Dashboard View
# ==============================================================================

@login_required
def dashboard_view(request):
    """Main dashboard displaying live metrics, charts, and recent activity."""
    period_filter = request.GET.get('period', 'this_month')
    custom_start = request.GET.get('start_date')
    custom_end = request.GET.get('end_date')

    start_date, end_date = FinanceService.get_date_range(period_filter, custom_start, custom_end)
    summary = FinanceService.get_dashboard_summary(request.user, start_date, end_date)
    chart_data = FinanceService.get_chart_data(request.user, start_date, end_date)

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).select_related('category')[:8]

    return render(request, 'expenses/dashboard.html', {
        'summary': summary,
        'chart_data': chart_data,
        'recent_transactions': recent_transactions,
        'period_filter': period_filter,
        'custom_start': custom_start or '',
        'custom_end': custom_end or '',
    })


# ==============================================================================
# Transactions Views
# ==============================================================================

@login_required
def transaction_list_view(request):
    """
    Searchable, filterable, sortable, and paginated transactions list.
    """
    transactions = Transaction.objects.filter(user=request.user).select_related('category')

    # Filters
    search_query = request.GET.get('q', '').strip()
    tx_type = request.GET.get('type', '').strip()
    category_id = request.GET.get('category', '').strip()
    payment_method = request.GET.get('payment_method', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    sort_by = request.GET.get('sort', '-transaction_date').strip()

    if search_query:
        transactions = transactions.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(reference_number__icontains=search_query)
        )

    if tx_type in ('income', 'expense'):
        transactions = transactions.filter(transaction_type=tx_type)

    if category_id:
        transactions = transactions.filter(category_id=category_id)

    if payment_method:
        transactions = transactions.filter(payment_method=payment_method)

    if start_date:
        transactions = transactions.filter(transaction_date__gte=start_date)

    if end_date:
        transactions = transactions.filter(transaction_date__lte=end_date)

    # Allowed sort keys
    valid_sorts = {
        'date_desc': '-transaction_date',
        'date_asc': 'transaction_date',
        'amount_desc': '-amount',
        'amount_asc': 'amount',
        'title_asc': 'title',
    }
    order_field = valid_sorts.get(sort_by, '-transaction_date')
    transactions = transactions.order_by(order_field, '-created_at')

    # Aggregations for the currently filtered result set
    filtered_income = transactions.filter(transaction_type='income').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    filtered_expense = transactions.filter(transaction_type='expense').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    filtered_net = filtered_income - filtered_expense

    # Pagination
    paginator = Paginator(transactions, 10)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    categories = Category.objects.filter(user=request.user)

    return render(request, 'expenses/transaction_list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'tx_type': tx_type,
        'selected_category': category_id,
        'selected_pm': payment_method,
        'start_date': start_date,
        'end_date': end_date,
        'sort_by': sort_by,
        'filtered_income': filtered_income,
        'filtered_expense': filtered_expense,
        'filtered_net': filtered_net,
        'payment_methods': Transaction.PAYMENT_METHODS,
    })


@login_required
def transaction_create_view(request):
    """Create a new income or expense transaction."""
    default_type = request.GET.get('type', 'expense')
    if default_type not in ('income', 'expense'):
        default_type = 'expense'

    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            tx = form.save()
            messages.success(request, f"Transaction '{tx.title}' of ₹{tx.amount:,.2f} recorded successfully.")
            return redirect('transaction-list')
        else:
            messages.error(request, "Please resolve the form errors below.")
    else:
        form = TransactionForm(user=request.user, initial={'transaction_type': default_type})

    return render(request, 'expenses/transaction_form.html', {
        'form': form,
        'title': 'Add Transaction',
        'is_edit': False,
    })


@login_required
def transaction_update_view(request, pk):
    """Edit an existing transaction."""
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)

    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=tx, user=request.user)
        if form.is_valid():
            tx = form.save()
            messages.success(request, f"Transaction '{tx.title}' updated successfully.")
            return redirect('transaction-list')
        else:
            messages.error(request, "Failed to update transaction. Please verify inputs.")
    else:
        form = TransactionForm(instance=tx, user=request.user)

    return render(request, 'expenses/transaction_form.html', {
        'form': form,
        'title': 'Edit Transaction',
        'transaction': tx,
        'is_edit': True,
    })


@login_required
def transaction_delete_view(request, pk):
    """Delete a transaction with confirmation."""
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)

    if request.method == 'POST':
        title = tx.title
        amount = tx.amount
        tx.delete()
        messages.success(request, f"Transaction '{title}' (₹{amount:,.2f}) was permanently deleted.")
        return redirect('transaction-list')

    return render(request, 'expenses/transaction_confirm_delete.html', {'transaction': tx})


# ==============================================================================
# Category Views
# ==============================================================================

@login_required
def category_list_view(request):
    """List of all user categories with transaction usage metrics."""
    categories = Category.objects.filter(user=request.user).annotate(
        tx_count=Count('transactions'),
        total_spent=Sum('transactions__amount')
    ).order_by('category_type', 'name')

    expense_cats = [c for c in categories if c.category_type == 'expense']
    income_cats = [c for c in categories if c.category_type == 'income']

    return render(request, 'expenses/category_list.html', {
        'expense_categories': expense_cats,
        'income_categories': income_cats,
    })


@login_required
def category_create_view(request):
    """Create a custom category."""
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' created successfully.")
            return redirect('category-list')
        else:
            messages.error(request, "Please resolve the errors below.")
    else:
        cat_type = request.GET.get('type', 'expense')
        form = CategoryForm(user=request.user, initial={'category_type': cat_type, 'color': '#3b82f6'})

    return render(request, 'expenses/category_form.html', {
        'form': form,
        'title': 'Create New Category',
        'is_edit': False,
    })


@login_required
def category_update_view(request, pk):
    """Update an existing category."""
    cat = get_object_or_404(Category, pk=pk, user=request.user)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=cat, user=request.user)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' updated successfully.")
            return redirect('category-list')
        else:
            messages.error(request, "Failed to update category. Check the inputs below.")
    else:
        form = CategoryForm(instance=cat, user=request.user)

    return render(request, 'expenses/category_form.html', {
        'form': form,
        'title': f"Edit Category: {cat.name}",
        'category': cat,
        'is_edit': True,
    })


@login_required
def category_delete_view(request, pk):
    """Safely delete category or inform user if transactions exist."""
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    tx_count = cat.transactions.count()

    if request.method == 'POST':
        if tx_count > 0:
            messages.error(
                request,
                f"Cannot delete '{cat.name}' because {tx_count} transaction(s) are linked to it. Please reassign or delete these transactions first."
            )
            return redirect('category-list')

        name = cat.name
        cat.delete()
        messages.success(request, f"Category '{name}' was deleted.")
        return redirect('category-list')

    return render(request, 'expenses/category_confirm_delete.html', {
        'category': cat,
        'tx_count': tx_count,
    })


# ==============================================================================
# Budget Views
# ==============================================================================

@login_required
def budget_list_view(request):
    """List of all user budgets with real spending, remaining limits, and progress bars."""
    budgets = Budget.objects.filter(user=request.user).select_related('category')
    
    budget_items = []
    total_budget_limit = Decimal('0.00')
    total_spent_across_budgets = Decimal('0.00')

    for b in budgets:
        spent = b.get_spent_amount()
        rem = b.get_remaining_amount()
        pct = b.get_percentage_spent()
        status = b.get_status()

        total_budget_limit += b.amount_limit
        total_spent_across_budgets += spent

        budget_items.append({
            'budget': b,
            'spent': spent,
            'remaining': rem,
            'percentage': pct,
            'status': status,
        })

    return render(request, 'expenses/budget_list.html', {
        'budget_items': budget_items,
        'total_budget_limit': total_budget_limit,
        'total_spent_across_budgets': total_spent_across_budgets,
        'remaining_overall': total_budget_limit - total_spent_across_budgets,
    })


@login_required
def budget_create_view(request):
    """Create a new spending budget."""
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            b = form.save()
            messages.success(request, f"Budget '{b.name}' set for ₹{b.amount_limit:,.2f}.")
            return redirect('budget-list')
        else:
            messages.error(request, "Please correct the errors in the budget form.")
    else:
        # Default start and end date for current month
        today = timezone.now().date()
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(day=31)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timezone.timedelta(days=1)

        form = BudgetForm(user=request.user, initial={
            'start_date': start_date,
            'end_date': end_date,
            'period': 'monthly',
        })

    return render(request, 'expenses/budget_form.html', {
        'form': form,
        'title': 'Create New Budget',
        'is_edit': False,
    })


@login_required
def budget_update_view(request, pk):
    """Edit an existing budget."""
    b = get_object_or_404(Budget, pk=pk, user=request.user)

    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=b, user=request.user)
        if form.is_valid():
            b = form.save()
            messages.success(request, f"Budget '{b.name}' updated successfully.")
            return redirect('budget-list')
        else:
            messages.error(request, "Failed to update budget. Check your inputs.")
    else:
        form = BudgetForm(instance=b, user=request.user)

    return render(request, 'expenses/budget_form.html', {
        'form': form,
        'title': f"Edit Budget: {b.name}",
        'budget': b,
        'is_edit': True,
    })


@login_required
def budget_delete_view(request, pk):
    """Delete a budget target."""
    b = get_object_or_404(Budget, pk=pk, user=request.user)

    if request.method == 'POST':
        name = b.name
        b.delete()
        messages.success(request, f"Budget '{name}' was removed.")
        return redirect('budget-list')

    return render(request, 'expenses/budget_confirm_delete.html', {'budget': b})


# ==============================================================================
# Analytics & Reports Views
# ==============================================================================

@login_required
def analytics_view(request):
    """Dedicated interactive analytics dashboard powered by Chart.js."""
    period_filter = request.GET.get('period', 'this_month')
    custom_start = request.GET.get('start_date')
    custom_end = request.GET.get('end_date')

    start_date, end_date = FinanceService.get_date_range(period_filter, custom_start, custom_end)
    summary = FinanceService.get_dashboard_summary(request.user, start_date, end_date)
    chart_data = FinanceService.get_chart_data(request.user, start_date, end_date)

    return render(request, 'expenses/analytics.html', {
        'summary': summary,
        'chart_data': chart_data,
        'period_filter': period_filter,
        'custom_start': custom_start or '',
        'custom_end': custom_end or '',
    })


@login_required
def reports_view(request):
    """
    Financial reports page displaying monthly, yearly, category-wise,
    and payment breakdown summaries with one-click secure CSV export.
    """
    period_filter = request.GET.get('period', 'this_month')
    custom_start = request.GET.get('start_date')
    custom_end = request.GET.get('end_date')

    start_date, end_date = FinanceService.get_date_range(period_filter, custom_start, custom_end)
    summary = FinanceService.get_dashboard_summary(request.user, start_date, end_date)

    # Detailed Category Breakdown Table
    cat_summary = Transaction.objects.filter(
        user=request.user,
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    ).values(
        'category__name', 'category__category_type', 'category__color'
    ).annotate(
        total_amount=Sum('amount'),
        tx_count=Count('id')
    ).order_by('-total_amount')

    # Payment Methods Table
    pm_summary = Transaction.objects.filter(
        user=request.user,
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    ).values(
        'payment_method', 'transaction_type'
    ).annotate(
        total_amount=Sum('amount'),
        tx_count=Count('id')
    ).order_by('-total_amount')

    pm_dict = dict(Transaction.PAYMENT_METHODS)
    formatted_pm_summary = []
    for item in pm_summary:
        formatted_pm_summary.append({
            'method_name': pm_dict.get(item['payment_method'], item['payment_method'].title()),
            'type': item['transaction_type'],
            'total_amount': item['total_amount'],
            'tx_count': item['tx_count'],
        })

    return render(request, 'expenses/reports.html', {
        'summary': summary,
        'category_reports': cat_summary,
        'payment_reports': formatted_pm_summary,
        'period_filter': period_filter,
        'custom_start': custom_start or '',
        'custom_end': custom_end or '',
    })


@login_required
def export_csv_view(request):
    """
    Downloads filtered transactions as a formula-injection-safe CSV file.
    """
    tx_query = Transaction.objects.filter(user=request.user).select_related('category')

    search = request.GET.get('q', '').strip()
    tx_type = request.GET.get('type', '').strip()
    category_id = request.GET.get('category', '').strip()
    payment_method = request.GET.get('payment_method', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    if search:
        tx_query = tx_query.filter(Q(title__icontains=search) | Q(description__icontains=search))
    if tx_type in ('income', 'expense'):
        tx_query = tx_query.filter(transaction_type=tx_type)
    if category_id:
        tx_query = tx_query.filter(category_id=category_id)
    if payment_method:
        tx_query = tx_query.filter(payment_method=payment_method)
    if start_date:
        tx_query = tx_query.filter(transaction_date__gte=start_date)
    if end_date:
        tx_query = tx_query.filter(transaction_date__lte=end_date)

    csv_data = FinanceService.generate_csv_export(tx_query)
    filename = f"spendwise_export_{request.user.username}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"

    response = HttpResponse(csv_data, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
