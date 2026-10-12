"""
Django REST Framework API views for SpendWise.
Provides versioned /api/v1/ endpoints for Transactions, Categories, Budgets, Dashboard, Analytics, and CSV Export.
"""

from decimal import Decimal
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import Category, Transaction, Budget
from .serializers import CategorySerializer, TransactionSerializer, BudgetSerializer
from .permissions import IsOwner
from .services import FinanceService


class CustomAuthToken(ObtainAuthToken):
    """
    Returns an API authentication token for a valid username and password.
    """
    @extend_schema(
        description="Obtain API token by submitting valid username and password.",
        responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'email': user.email
        })


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing user-specific categories.
    """
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category_type']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        # Safe deletion policy: verify transaction dependencies
        tx_count = category.transactions.count()
        if tx_count > 0:
            return Response(
                {
                    'error': f"Cannot delete category '{category.name}' because it has {tx_count} associated transaction(s). Please reassign or delete transactions first."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class TransactionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing user transactions (Income and Expense).
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'category', 'payment_method']
    search_fields = ['title', 'description', 'reference_number']
    ordering_fields = ['transaction_date', 'amount', 'created_at']
    ordering = ['-transaction_date', '-created_at']

    def get_queryset(self):
        user = self.request.user
        queryset = Transaction.objects.filter(user=user).select_related('category')
        
        # Optional date range query params
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(transaction_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(transaction_date__lte=end_date)

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BudgetViewSet(viewsets.ModelViewSet):
    """
    API endpoint for setting and tracking budget thresholds.
    """
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['period', 'category']
    search_fields = ['name']
    ordering_fields = ['start_date', 'amount_limit', 'created_at']
    ordering = ['-start_date']

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user).select_related('category')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DashboardSummaryAPIView(APIView):
    """
    API endpoint providing aggregated dashboard summary statistics.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter('filter', OpenApiTypes.STR, description='Period filter: this_month, last_month, last_3_months, this_year, custom, all_time'),
            OpenApiParameter('start_date', OpenApiTypes.DATE, description='Custom start date (YYYY-MM-DD)'),
            OpenApiParameter('end_date', OpenApiTypes.DATE, description='Custom end date (YYYY-MM-DD)'),
        ]
    )
    def get(self, request, *args, **kwargs):
        period_filter = request.query_params.get('filter', 'this_month')
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')

        start_date, end_date = FinanceService.get_date_range(period_filter, start_str, end_str)
        summary = FinanceService.get_dashboard_summary(request.user, start_date, end_date)

        data = {
            'period_filter': period_filter,
            'start_date': str(summary['period_start']),
            'end_date': str(summary['period_end']),
            'period_income': float(summary['period_income']),
            'period_expense': float(summary['period_expense']),
            'period_savings': float(summary['period_savings']),
            'savings_rate': summary['savings_rate'],
            'all_time_balance': float(summary['all_time_balance']),
            'all_time_income': float(summary['all_time_income']),
            'all_time_expense': float(summary['all_time_expense']),
            'prev_month_expense': float(summary['prev_month_expense']),
            'expense_diff_percentage': summary['expense_diff_percentage'],
            'budgets': summary['active_budgets'],
            'total_budget_limit': float(summary['total_budget_limit']),
            'total_budget_spent': float(summary['total_budget_spent']),
            'remaining_total_budget': float(summary['remaining_total_budget']),
        }
        return Response(data)


class AnalyticsAPIView(APIView):
    """
    API endpoint providing datasets for charts and financial analytics.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter('filter', OpenApiTypes.STR, description='Period filter: this_month, last_month, last_3_months, this_year, custom, all_time'),
            OpenApiParameter('start_date', OpenApiTypes.DATE, description='Custom start date (YYYY-MM-DD)'),
            OpenApiParameter('end_date', OpenApiTypes.DATE, description='Custom end date (YYYY-MM-DD)'),
        ]
    )
    def get(self, request, *args, **kwargs):
        period_filter = request.query_params.get('filter', 'this_month')
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')

        start_date, end_date = FinanceService.get_date_range(period_filter, start_str, end_str)
        chart_data = FinanceService.get_chart_data(request.user, start_date, end_date)

        return Response({
            'period_filter': period_filter,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'charts': chart_data
        })


class ExportTransactionsAPIView(APIView):
    """
    API endpoint to export filtered transactions in CSV format.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter('type', OpenApiTypes.STR, description='Transaction type: income or expense'),
            OpenApiParameter('category', OpenApiTypes.INT, description='Category ID'),
            OpenApiParameter('payment_method', OpenApiTypes.STR, description='Payment method'),
            OpenApiParameter('start_date', OpenApiTypes.DATE, description='Start date YYYY-MM-DD'),
            OpenApiParameter('end_date', OpenApiTypes.DATE, description='End date YYYY-MM-DD'),
        ]
    )
    def get(self, request, *args, **kwargs):
        tx_query = Transaction.objects.filter(user=request.user).select_related('category')

        tx_type = request.query_params.get('type')
        category_id = request.query_params.get('category')
        payment_method = request.query_params.get('payment_method')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

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

        csv_content = FinanceService.generate_csv_export(tx_query)

        filename = f"spendwise_transactions_{request.user.username}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
