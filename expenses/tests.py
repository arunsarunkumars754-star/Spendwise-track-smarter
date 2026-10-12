"""
Comprehensive automated test suite for SpendWise application.
Covers authentication, models, services, views, REST APIs, CSV export, validation, and security isolation.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import (
    Budget,
    Category,
    Transaction,
    create_default_categories_for_user,
)


class SpendWiseModelTests(TestCase):
    """Unit tests for models and data integrity constraints."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='alice', password='Password@123')
        self.user2 = User.objects.create_user(username='bob', password='Password@123')
        create_default_categories_for_user(self.user1)
        create_default_categories_for_user(self.user2)

    def test_default_categories_created(self):
        """Verify that default categories are correctly populated for new users."""
        cats1 = Category.objects.filter(user=self.user1)
        self.assertGreater(cats1.count(), 10)
        self.assertTrue(cats1.filter(name='Food & Dining', category_type='expense').exists())
        self.assertTrue(cats1.filter(name='Salary', category_type='income').exists())

    def test_transaction_creation_and_validation(self):
        """Test valid transaction creation and ownership validation."""
        food_cat = Category.objects.get(user=self.user1, name='Food & Dining')
        tx = Transaction.objects.create(
            user=self.user1,
            category=food_cat,
            transaction_type='expense',
            title='Lunch with Colleagues',
            amount=Decimal('450.00'),
            transaction_date=date.today(),
            payment_method='upi'
        )
        self.assertEqual(tx.amount, Decimal('450.00'))
        self.assertEqual(tx.category.user, self.user1)

    def test_invalid_amount_validation(self):
        """Test that amounts less than or equal to zero raise ValidationError."""
        food_cat = Category.objects.get(user=self.user1, name='Food & Dining')
        with self.assertRaises(ValidationError):
            tx = Transaction(
                user=self.user1,
                category=food_cat,
                transaction_type='expense',
                title='Zero Amount Transaction',
                amount=Decimal('0.00'),
                transaction_date=date.today()
            )
            tx.full_clean()

    def test_cross_user_category_assignment_prevented(self):
        """Test that user cannot assign another user's category to their transaction."""
        bob_cat = Category.objects.get(user=self.user2, name='Food & Dining')
        with self.assertRaises(ValidationError):
            tx = Transaction(
                user=self.user1,
                category=bob_cat,
                transaction_type='expense',
                title='Stealing Category',
                amount=Decimal('100.00'),
                transaction_date=date.today()
            )
            tx.full_clean()

    def test_category_type_mismatch_prevented(self):
        """Test that category type must match transaction type."""
        salary_cat = Category.objects.get(user=self.user1, name='Salary', category_type='income')
        with self.assertRaises(ValidationError):
            tx = Transaction(
                user=self.user1,
                category=salary_cat,
                transaction_type='expense', # Mismatch!
                title='Invalid Expense under Salary',
                amount=Decimal('500.00'),
                transaction_date=date.today()
            )
            tx.full_clean()

    def test_budget_calculations_and_status(self):
        """Test budget spent, remaining, percentage, and alert status calculation."""
        food_cat = Category.objects.get(user=self.user1, name='Food & Dining')
        start = date.today().replace(day=1)
        end = start + timedelta(days=28)

        budget = Budget.objects.create(
            user=self.user1,
            category=food_cat,
            name='Dining Budget',
            amount_limit=Decimal('1000.00'),
            period='monthly',
            start_date=start,
            end_date=end
        )

        self.assertEqual(budget.get_spent_amount(), Decimal('0.00'))
        self.assertEqual(budget.get_status(), 'normal')

        # Add 850 expense -> 85% spent (warning status)
        Transaction.objects.create(
            user=self.user1,
            category=food_cat,
            transaction_type='expense',
            title='Dinner',
            amount=Decimal('850.00'),
            transaction_date=start + timedelta(days=2),
            payment_method='upi'
        )
        self.assertEqual(budget.get_spent_amount(), Decimal('850.00'))
        self.assertEqual(budget.get_percentage_spent(), 85.0)
        self.assertEqual(budget.get_status(), 'warning')

        # Add another 200 expense -> 1050 spent (exceeded status)
        Transaction.objects.create(
            user=self.user1,
            category=food_cat,
            transaction_type='expense',
            title='Brunch',
            amount=Decimal('200.00'),
            transaction_date=start + timedelta(days=3),
            payment_method='upi'
        )
        self.assertEqual(budget.get_spent_amount(), Decimal('1050.00'))
        self.assertEqual(budget.get_status(), 'exceeded')


class SpendWiseWebViewsTests(TestCase):
    """Integration tests for web authentication and web pages."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='Password@123', email='tester@test.com')
        create_default_categories_for_user(self.user)
        self.food_cat = Category.objects.get(user=self.user, name='Food & Dining')

    def test_anonymous_redirected_to_login(self):
        """Verify unauthenticated users cannot access dashboard or transactions."""
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

        resp2 = self.client.get(reverse('transaction-list'))
        self.assertEqual(resp2.status_code, 302)

    def test_user_login_and_dashboard_render(self):
        """Verify successful user authentication and dashboard view rendering."""
        login_success = self.client.login(username='tester', password='Password@123')
        self.assertTrue(login_success)

        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Financial Overview")
        self.assertContains(resp, "Period Income")

    def test_transaction_crud_web_flow(self):
        """Test transaction creation, updating, and deletion via web views."""
        self.client.login(username='tester', password='Password@123')

        # 1. Create transaction
        create_resp = self.client.post(reverse('transaction-create'), {
            'title': 'Test Grocery Run',
            'amount': '1250.50',
            'transaction_type': 'expense',
            'category': self.food_cat.id,
            'transaction_date': date.today().strftime('%Y-%m-%d'),
            'payment_method': 'upi',
            'reference_number': 'REF123',
            'description': 'Weekly purchase'
        }, follow=True)
        self.assertEqual(create_resp.status_code, 200)
        self.assertTrue(Transaction.objects.filter(user=self.user, title='Test Grocery Run').exists())

        tx = Transaction.objects.get(user=self.user, title='Test Grocery Run')

        # 2. Update transaction
        edit_resp = self.client.post(reverse('transaction-update', args=[tx.pk]), {
            'title': 'Updated Grocery Run',
            'amount': '1400.00',
            'transaction_type': 'expense',
            'category': self.food_cat.id,
            'transaction_date': date.today().strftime('%Y-%m-%d'),
            'payment_method': 'upi',
        }, follow=True)
        self.assertEqual(edit_resp.status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.title, 'Updated Grocery Run')
        self.assertEqual(tx.amount, Decimal('1400.00'))

        # 3. Delete transaction
        del_resp = self.client.post(reverse('transaction-delete', args=[tx.pk]), follow=True)
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(Transaction.objects.filter(pk=tx.pk).exists())

    def test_cross_user_isolation_web(self):
        """Verify that User A cannot edit or delete User B's transaction."""
        user_b = User.objects.create_user(username='other', password='Password@123')
        create_default_categories_for_user(user_b)
        cat_b = Category.objects.get(user=user_b, name='Food & Dining')

        tx_b = Transaction.objects.create(
            user=user_b,
            category=cat_b,
            transaction_type='expense',
            title="User B's Private Expense",
            amount=Decimal('999.00'),
            transaction_date=date.today(),
            payment_method='cash'
        )

        # Log in as tester (User A)
        self.client.login(username='tester', password='Password@123')

        # Attempt to edit User B's transaction
        resp_edit = self.client.get(reverse('transaction-update', args=[tx_b.pk]))
        self.assertEqual(resp_edit.status_code, 404) # Not found in user A's scope

        # Attempt to delete User B's transaction
        resp_del = self.client.post(reverse('transaction-delete', args=[tx_b.pk]))
        self.assertEqual(resp_del.status_code, 404)
        self.assertTrue(Transaction.objects.filter(pk=tx_b.pk).exists())

    def test_csv_export_and_formula_injection_protection(self):
        """Verify CSV export and formula injection sanitization."""
        self.client.login(username='tester', password='Password@123')

        # Transaction with potentially malicious formula title
        Transaction.objects.create(
            user=self.user,
            category=self.food_cat,
            transaction_type='expense',
            title='=SUM(A1:A10)',
            amount=Decimal('50.00'),
            transaction_date=date.today(),
            payment_method='upi'
        )

        resp = self.client.get(reverse('export-csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        content = resp.content.decode('utf-8-sig')

        # Verify header presence
        self.assertIn("Transaction ID", content)
        self.assertIn("Amount (INR)", content)
        # Verify formula was prepended with single quote apostrophe
        self.assertIn("'=SUM(A1:A10)", content)


class SpendWiseAPITests(TestCase):
    """Integration tests for Django REST Framework API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='api_alice', password='Password@123')
        self.user2 = User.objects.create_user(username='api_bob', password='Password@123')
        create_default_categories_for_user(self.user1)
        create_default_categories_for_user(self.user2)

        self.token1 = Token.objects.create(user=self.user1)
        self.token2 = Token.objects.create(user=self.user2)

        self.cat1 = Category.objects.get(user=self.user1, name='Food & Dining')
        self.cat2 = Category.objects.get(user=self.user2, name='Food & Dining')

    def test_unauthenticated_api_request_rejected(self):
        """Verify unauthenticated API requests are rejected (401 or 403)."""
        resp = self.client.get('/api/v1/transactions/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_api_token_authentication_and_crud(self):
        """Verify Token authentication and Transaction CRUD via REST API."""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)

        # 1. Create Transaction
        create_payload = {
            'title': 'API Dinner',
            'amount': '750.00',
            'transaction_type': 'expense',
            'category': self.cat1.id,
            'transaction_date': str(date.today()),
            'payment_method': 'credit_card',
            'reference_number': 'API-REF-01',
            'description': 'Created via REST API'
        }
        resp = self.client.post('/api/v1/transactions/', create_payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        tx_id = resp.data['id']
        self.assertEqual(resp.data['title'], 'API Dinner')

        # 2. List Transactions (User 1 sees only own)
        resp_list = self.client.get('/api/v1/transactions/')
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_list.data['count'], 1)

        # 3. User 2 cannot access User 1's transaction
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token2.key)
        resp_other = self.client.get(f'/api/v1/transactions/{tx_id}/')
        self.assertEqual(resp_other.status_code, status.HTTP_404_NOT_FOUND)

    def test_dashboard_and_analytics_api_endpoints(self):
        """Verify /api/v1/dashboard/summary/ and /api/v1/analytics/ responses."""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)

        # Add income and expense
        salary_cat = Category.objects.get(user=self.user1, name='Salary')
        Transaction.objects.create(
            user=self.user1,
            category=salary_cat,
            transaction_type='income',
            title='Salary Deposit',
            amount=Decimal('50000.00'),
            transaction_date=date.today(),
            payment_method='bank_transfer'
        )

        resp_summary = self.client.get('/api/v1/dashboard/summary/?filter=this_month')
        self.assertEqual(resp_summary.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_summary.data['period_income'], 50000.0)

        resp_analytics = self.client.get('/api/v1/analytics/?filter=this_month')
        self.assertEqual(resp_analytics.status_code, status.HTTP_200_OK)
        self.assertIn('charts', resp_analytics.data)
        self.assertIn('category_breakdown', resp_analytics.data['charts'])
