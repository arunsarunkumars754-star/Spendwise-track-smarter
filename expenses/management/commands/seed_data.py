"""
Management command to seed SpendWise with rich, realistic demonstration data.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.utils import timezone

from expenses.models import Category, Transaction, Budget, UserProfile, create_default_categories_for_user


class Command(BaseCommand):
    help = 'Seeds SpendWise with demo user, categories, budgets, and transactions for demonstration and testing.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing demo data for SpendWise..."))

        username = 'demo'
        password = 'DemoUser@123'
        email = 'demo@spendwise.local'

        user, created = User.objects.get_or_create(username=username, defaults={
            'first_name': 'Aarav',
            'last_name': 'Sharma',
            'email': email,
        })
        user.set_password(password)
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={
            'currency': 'INR',
            'phone': '+91 9876543210',
            'bio': 'AIML Student & Software Developer tracking financial health with SpendWise.',
        })

        # Generate API Token
        token, _ = Token.objects.get_or_create(user=user)

        # Seed categories
        create_default_categories_for_user(user)

        # Retrieve categories map
        cat_map = {c.name: c for c in Category.objects.filter(user=user)}

        # Clear existing transactions and budgets for clean seed
        Transaction.objects.filter(user=user).delete()
        Budget.objects.filter(user=user).delete()

        today = timezone.now().date()

        # Seed monthly salary and freelance income for past 4 months
        for i in range(4):
            # calculate past month date
            m_date = today.replace(day=1) - timedelta(days=30 * i)
            # Salary
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Salary'),
                transaction_type='income',
                title=f'Monthly Tech Stipend & Salary - {m_date.strftime("%B")}',
                amount=Decimal('85000.00'),
                transaction_date=m_date.replace(day=1),
                payment_method='bank_transfer',
                reference_number=f'SAL-2026-{m_date.month:02d}-001',
                description='Direct deposit from software engineering employer.'
            )
            # Freelance
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Freelance & Consulting'),
                transaction_type='income',
                title=f'Freelance AI Project Milestone - {m_date.strftime("%B")}',
                amount=Decimal('24500.00'),
                transaction_date=m_date.replace(day=12),
                payment_method='upi',
                reference_number=f'UPI-{m_date.month:02d}8827',
                description='Consulting milestone deliverable for client.'
            )

        # Realistic Expenses in current and past months
        sample_expenses = [
            # Current month expenses
            ('Housing & Rent', 'Apartment Rent & Maintenance', Decimal('22000.00'), 2, 'bank_transfer', 'RENT-OCT-01'),
            ('Utilities & Bills', 'Fiber Internet & Electric Bill', Decimal('2450.00'), 4, 'upi', 'UPI-BBPS-771'),
            ('Groceries', 'Weekly Supermarket Grocery Basket', Decimal('4850.00'), 5, 'debit_card', 'POS-STORE-992'),
            ('Food & Dining', 'Dinner with University Friends', Decimal('1850.00'), 6, 'upi', 'UPI-DINING-321'),
            ('Transportation', 'Metro Pass Recharge & Cab Fares', Decimal('1200.00'), 8, 'upi', 'UPI-METRO-401'),
            ('Shopping', 'Wireless Noise-Canceling Headphones', Decimal('6499.00'), 9, 'credit_card', 'AMZN-98234'),
            ('Healthcare & Medical', 'Routine Health Checkup & Vitamins', Decimal('1650.00'), 10, 'debit_card', 'MED-LAB-12'),
            ('Entertainment', 'Cloud & Media Subscriptions', Decimal('899.00'), 11, 'credit_card', 'SUB-OTT-09'),
            ('Education & Books', 'Deep Learning & LLM Architecture Book', Decimal('1450.00'), 12, 'upi', 'BOOK-AI-202'),
            ('Food & Dining', 'Weekend Cafe Work Session', Decimal('680.00'), 13, 'cash', ''),
            ('Groceries', 'Fresh Produce & Dairy Restock', Decimal('2100.00'), 14, 'upi', 'UPI-MART-55'),

            # Prior month expenses
            ('Housing & Rent', 'Apartment Rent & Maintenance', Decimal('22000.00'), 32, 'bank_transfer', 'RENT-PREV-01'),
            ('Groceries', 'Monthly Grocery Restock', Decimal('8900.00'), 35, 'debit_card', 'POS-STORE-881'),
            ('Food & Dining', 'Team Celebration Dinner', Decimal('3200.00'), 38, 'credit_card', 'REST-8871'),
            ('Transportation', 'Intercity Train Tickets', Decimal('2150.00'), 41, 'upi', 'IRCTC-7729'),
            ('Utilities & Bills', 'Mobile Postpaid & Electricity', Decimal('2100.00'), 44, 'upi', 'UPI-BILL-33'),
            ('Shopping', 'Ergonomic Desk Chair', Decimal('8500.00'), 48, 'credit_card', 'SHOP-FURN-12'),
            ('Healthcare & Medical', 'Dental Cleaning', Decimal('1200.00'), 52, 'cash', ''),

            # 2 months ago
            ('Housing & Rent', 'Apartment Rent & Maintenance', Decimal('22000.00'), 62, 'bank_transfer', 'RENT-PAST-01'),
            ('Groceries', 'Supermarket Supplies', Decimal('7800.00'), 65, 'debit_card', 'POS-SUPER-12'),
            ('Education & Books', 'Online Cloud Certification Exam Fee', Decimal('9200.00'), 68, 'credit_card', 'EXAM-AWS-99'),
            ('Food & Dining', 'Family Weekend Dinner', Decimal('2600.00'), 72, 'upi', 'UPI-FOOD-11'),
        ]

        for cat_name, title, amount, days_ago, pm, ref in sample_expenses:
            tx_date = today - timedelta(days=days_ago)
            category = cat_map.get(cat_name)
            if category:
                Transaction.objects.create(
                    user=user,
                    category=category,
                    transaction_type='expense',
                    title=title,
                    amount=amount,
                    transaction_date=tx_date,
                    payment_method=pm,
                    reference_number=ref,
                    description=f"Recorded expense for {cat_name.lower()}."
                )

        # Seed Budgets for current month
        m_start = today.replace(day=1)
        if today.month == 12:
            m_end = today.replace(day=31)
        else:
            m_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        # 1. Overall Monthly Expense Budget
        Budget.objects.create(
            user=user,
            category=None,
            name='Monthly Spending Ceiling',
            amount_limit=Decimal('50000.00'),
            period='monthly',
            start_date=m_start,
            end_date=m_end,
        )

        # 2. Category Budget: Food & Dining (Warning state >= 80%)
        food_cat = cat_map.get('Food & Dining')
        if food_cat:
            Budget.objects.create(
                user=user,
                category=food_cat,
                name='Dining & Cafes Allowance',
                amount_limit=Decimal('3000.00'), # spent is ~2530 (84% -> Warning status!)
                period='monthly',
                start_date=m_start,
                end_date=m_end,
            )

        # 3. Category Budget: Groceries (Normal state < 80%)
        groc_cat = cat_map.get('Groceries')
        if groc_cat:
            Budget.objects.create(
                user=user,
                category=groc_cat,
                name='Groceries & Staples',
                amount_limit=Decimal('12000.00'),
                period='monthly',
                start_date=m_start,
                end_date=m_end,
            )

        # 4. Category Budget: Shopping (Exceeded state >= 100%)
        shop_cat = cat_map.get('Shopping')
        if shop_cat:
            Budget.objects.create(
                user=user,
                category=shop_cat,
                name='Personal Shopping Limit',
                amount_limit=Decimal('5000.00'), # spent is 6499 (130% -> Exceeded status!)
                period='monthly',
                start_date=m_start,
                end_date=m_end,
            )

        self.stdout.write(self.style.SUCCESS("Demo data successfully created!"))
        self.stdout.write(self.style.SUCCESS(f"User: {username} | Password: {password}"))
        self.stdout.write(self.style.SUCCESS(f"API Token: {token.key}"))
