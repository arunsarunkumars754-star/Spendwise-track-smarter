"""
Business logic and analytics service layer for SpendWise.
Encapsulates financial aggregations, date filtering, chart metrics, and secure CSV generation.
"""

import csv
import io
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import Transaction, Budget, Category


class FinanceService:
    """
    Core service for computing metrics, period aggregations, and budget summaries.
    """

    @staticmethod
    def get_date_range(filter_type, custom_start=None, custom_end=None):
        """
        Calculates start and end dates based on filter criteria.
        Supported filters: 'this_month', 'last_month', 'last_3_months', 'this_year', 'custom', 'all_time'.
        """
        today = timezone.now().date()
        
        if filter_type == 'last_month':
            first_day_current_month = today.replace(day=1)
            last_day_prev_month = first_day_current_month - timedelta(days=1)
            start_date = last_day_prev_month.replace(day=1)
            end_date = last_day_prev_month
        elif filter_type == 'last_3_months':
            start_date = (today.replace(day=1) - timedelta(days=70)).replace(day=1)
            end_date = today
        elif filter_type == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        elif filter_type == 'custom' and custom_start and custom_end:
            try:
                if isinstance(custom_start, str):
                    start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
                else:
                    start_date = custom_start

                if isinstance(custom_end, str):
                    end_date = datetime.strptime(custom_end, '%Y-%m-%d').date()
                else:
                    end_date = custom_end
            except (ValueError, TypeError):
                start_date = today.replace(day=1)
                end_date = today
        elif filter_type == 'all_time':
            start_date = date(2000, 1, 1)
            end_date = today
        else: # Default: 'this_month'
            start_date = today.replace(day=1)
            # Find last day of this month
            if today.month == 12:
                end_date = today.replace(day=31)
            else:
                next_month = today.replace(month=today.month + 1, day=1)
                end_date = next_month - timedelta(days=1)

        return start_date, end_date

    @staticmethod
    def get_dashboard_summary(user, start_date=None, end_date=None):
        """
        Computes financial summary for the dashboard:
        - Total income in period
        - Total expense in period
        - All-time balance (total recorded income - total recorded expense)
        - Period net savings (income - expense)
        - Savings rate percentage
        - Active budgets summary
        """
        if not start_date or not end_date:
            start_date, end_date = FinanceService.get_date_range('this_month')

        # Filtered period metrics
        period_txs = Transaction.objects.filter(
            user=user,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )

        period_income = period_txs.filter(transaction_type='income').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        period_expense = period_txs.filter(transaction_type='expense').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        period_savings = period_income - period_expense

        savings_rate = Decimal('0.0')
        if period_income > Decimal('0.00'):
            savings_rate = round(((period_income - period_expense) / period_income) * Decimal('100.0'), 1)

        # All-time metrics for true cumulative balance
        all_txs = Transaction.objects.filter(user=user)
        all_time_income = all_txs.filter(transaction_type='income').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        all_time_expense = all_txs.filter(transaction_type='expense').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        all_time_balance = all_time_income - all_time_expense

        # Previous month comparison for expense trends
        today = timezone.now().date()
        prev_month_start, prev_month_end = FinanceService.get_date_range('last_month')
        prev_month_expense = Transaction.objects.filter(
            user=user,
            transaction_type='expense',
            transaction_date__gte=prev_month_start,
            transaction_date__lte=prev_month_end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expense_diff_percentage = 0.0
        if prev_month_expense > Decimal('0.00'):
            diff = period_expense - prev_month_expense
            expense_diff_percentage = round(float((diff / prev_month_expense) * Decimal('100.0')), 1)

        # Active budgets in period
        active_budgets = Budget.objects.filter(
            user=user,
            start_date__lte=end_date,
            end_date__gte=start_date
        ).select_related('category')

        budget_summaries = []
        total_budget_limit = Decimal('0.00')
        total_budget_spent = Decimal('0.00')

        for b in active_budgets:
            spent = b.get_spent_amount()
            remaining = b.get_remaining_amount()
            pct = b.get_percentage_spent()
            status = b.get_status()
            
            total_budget_limit += b.amount_limit
            total_budget_spent += spent

            budget_summaries.append({
                'id': b.id,
                'name': b.name,
                'category_name': b.category.name if b.category else 'Overall',
                'category_color': b.category.color if b.category else '#3b82f6',
                'limit': float(b.amount_limit),
                'spent': float(spent),
                'remaining': float(remaining),
                'percentage': pct,
                'status': status,
                'period': b.get_period_display(),
            })

        remaining_total_budget = total_budget_limit - total_budget_spent

        return {
            'period_start': start_date,
            'period_end': end_date,
            'period_income': period_income,
            'period_expense': period_expense,
            'period_savings': period_savings,
            'savings_rate': float(savings_rate),
            'all_time_balance': all_time_balance,
            'all_time_income': all_time_income,
            'all_time_expense': all_time_expense,
            'prev_month_expense': prev_month_expense,
            'expense_diff_percentage': expense_diff_percentage,
            'active_budgets': budget_summaries,
            'total_budget_limit': total_budget_limit,
            'total_budget_spent': total_budget_spent,
            'remaining_total_budget': remaining_total_budget,
            'budget_count': len(budget_summaries),
        }

    @staticmethod
    def get_chart_data(user, start_date=None, end_date=None):
        """
        Aggregates data specifically structured for Chart.js renders:
        1. Category expense breakdown (Doughnut)
        2. Daily spending trend (Line)
        3. Monthly income vs expense (Bar)
        4. Payment method distribution (Polar/Pie)
        5. Top 5 spending categories (Bar)
        """
        if not start_date or not end_date:
            start_date, end_date = FinanceService.get_date_range('this_month')

        tx_query = Transaction.objects.filter(
            user=user,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )

        # 1. Category Expense Breakdown
        category_expenses = tx_query.filter(transaction_type='expense').values(
            'category__name', 'category__color'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')

        cat_labels = [c['category__name'] or 'Uncategorized' for c in category_expenses]
        cat_data = [float(c['total']) for c in category_expenses]
        cat_colors = [c['category__color'] or '#3b82f6' for c in category_expenses]

        # 2. Payment Method Distribution
        pm_data_qs = tx_query.filter(transaction_type='expense').values('payment_method').annotate(
            total=Sum('amount')
        ).order_by('-total')

        pm_dict = dict(Transaction.PAYMENT_METHODS)
        pm_labels = [pm_dict.get(p['payment_method'], p['payment_method'].title()) for p in pm_data_qs]
        pm_values = [float(p['total']) for p in pm_data_qs]

        # 3. Monthly Income vs Expense Trend (Last 6 Months)
        today = timezone.now().date()
        months_labels = []
        monthly_income_data = []
        monthly_expense_data = []

        # Generate last 6 months list
        for i in range(5, -1, -1):
            # calculate year and month
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            m_start = date(y, m, 1)
            if m == 12:
                m_end = date(y, 12, 31)
            else:
                m_end = date(y, m + 1, 1) - timedelta(days=1)

            month_label = m_start.strftime('%b %Y')
            months_labels.append(month_label)

            m_income = Transaction.objects.filter(
                user=user,
                transaction_type='income',
                transaction_date__gte=m_start,
                transaction_date__lte=m_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            m_expense = Transaction.objects.filter(
                user=user,
                transaction_type='expense',
                transaction_date__gte=m_start,
                transaction_date__lte=m_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            monthly_income_data.append(float(m_income))
            monthly_expense_data.append(float(m_expense))

        # 4. Daily Spending Trend in Current Period
        daily_trend = tx_query.filter(transaction_type='expense').values('transaction_date').annotate(
            daily_total=Sum('amount')
        ).order_by('transaction_date')

        daily_labels = [d['transaction_date'].strftime('%d %b') for d in daily_trend]
        daily_amounts = [float(d['daily_total']) for d in daily_trend]

        # 5. Top 5 Categories
        top_cats = category_expenses[:5]
        top_cat_labels = [c['category__name'] for c in top_cats]
        top_cat_data = [float(c['total']) for c in top_cats]

        return {
            'category_breakdown': {
                'labels': cat_labels,
                'data': cat_data,
                'colors': cat_colors,
            },
            'payment_methods': {
                'labels': pm_labels,
                'data': pm_values,
            },
            'monthly_comparison': {
                'labels': months_labels,
                'income': monthly_income_data,
                'expense': monthly_expense_data,
            },
            'daily_trend': {
                'labels': daily_labels,
                'data': daily_amounts,
            },
            'top_categories': {
                'labels': top_cat_labels,
                'data': top_cat_data,
            }
        }

    @staticmethod
    def generate_csv_export(transactions):
        """
        Generates a safe CSV byte stream with CSV formula injection protection.
        Leading characters '=', '+', '-', '@', '\t', '\r' are escaped with an apostrophe.
        """
        output = io.StringIO()
        writer = csv.writer(output, dialect='excel')

        # CSV Header
        writer.writerow([
            'Transaction ID',
            'Date',
            'Type',
            'Category',
            'Title',
            'Amount (INR)',
            'Payment Method',
            'Reference Number',
            'Description',
            'Created At'
        ])

        def sanitize_csv_field(val):
            """Sanitize against CSV Formula Injection."""
            if val is None:
                return ''
            text = str(val).strip()
            if text and text[0] in ('=', '+', '-', '@', '\t', '\r'):
                return f"'{text}"
            return text

        for tx in transactions:
            writer.writerow([
                sanitize_csv_field(tx.id),
                sanitize_csv_field(tx.transaction_date.strftime('%Y-%m-%d')),
                sanitize_csv_field(tx.get_transaction_type_display()),
                sanitize_csv_field(tx.category.name if tx.category else 'Uncategorized'),
                sanitize_csv_field(tx.title),
                f"{tx.amount:.2f}",
                sanitize_csv_field(tx.get_payment_method_display()),
                sanitize_csv_field(tx.reference_number),
                sanitize_csv_field(tx.description),
                sanitize_csv_field(tx.created_at.strftime('%Y-%m-%d %H:%M:%S')),
            ])

        return output.getvalue().encode('utf-8-sig') # UTF-8 with BOM for Excel compatibility
