"""
Database models for SpendWise Expense Tracker application.
Designed with strict user data isolation, database constraints, indexes, and validation.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """
    Extended user profile for additional metadata such as avatar, phone, and currency.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    currency = models.CharField(max_length=10, default='INR')
    bio = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        user_name = getattr(self.user, 'username', str(self.user))
        return f"{user_name}'s Profile"


class Category(models.Model):
    """
    User-specific category for classifying transactions (Income or Expense).
    """
    CATEGORY_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=10, choices=CATEGORY_TYPES, default='expense')
    description = models.TextField(blank=True, max_length=300)
    color = models.CharField(max_length=20, default='#3b82f6', help_text="Hex color code (e.g. #3b82f6)")
    icon = models.CharField(max_length=50, default='bi-tag', help_text="Bootstrap icon class (e.g. bi-cart)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name', 'category_type'],
                name='unique_user_category_name_and_type'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'category_type']),
            models.Index(fields=['user', 'name']),
        ]

    def __str__(self):
        type_display = self.get_category_type_display() if hasattr(self, 'get_category_type_display') else self.category_type
        return f"{self.name} ({type_display})"

    @property
    def transaction_count(self):
        """Returns the total number of transactions linked to this category."""
        txs = getattr(self, 'transactions', None)
        return txs.count() if txs is not None else 0


class Transaction(models.Model):
    """
    Financial transaction record (Income or Expense) strictly isolated per user.
    """
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('debit_card', 'Debit Card'),
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='transactions',
        help_text="Category must belong to the same user and match transaction type"
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, default='expense')
    title = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), message="Amount must be greater than zero.")]
    )
    description = models.TextField(blank=True)
    transaction_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='upi')
    reference_number = models.CharField(max_length=100, blank=True, help_text="Receipt/UPI/UTR/Invoice number")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'transaction_date']),
            models.Index(fields=['user', 'transaction_type']),
            models.Index(fields=['user', 'category']),
            models.Index(fields=['user', 'payment_method']),
        ]

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': 'Amount must be strictly greater than zero.'})

        if hasattr(self, 'category') and self.category:
            # Enforce user ownership of the selected category if user is assigned
            if self.user_id and self.category.user_id != self.user_id:
                raise ValidationError({'category': 'The selected category does not belong to your account.'})

            # Enforce category type matching transaction type
            if self.category.category_type != self.transaction_type:
                raise ValidationError({
                    'category': f"The selected category is configured for {self.category.get_category_type_display()}, but this transaction is marked as {self.get_transaction_type_display()}."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - ₹{self.amount} ({self.get_transaction_type_display()})"


class Budget(models.Model):
    """
    Budget target defined overall or for a specific category over a time period.
    """
    PERIOD_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='budgets',
        help_text="Leave blank to create an overall monthly or yearly expense budget."
    )
    name = models.CharField(max_length=150)
    amount_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), message="Budget limit must be greater than zero.")]
    )
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default='monthly')
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Budget'
        verbose_name_plural = 'Budgets'
        ordering = ['-start_date', 'name']
        indexes = [
            models.Index(fields=['user', 'start_date', 'end_date']),
            models.Index(fields=['user', 'category']),
        ]

    def clean(self):
        super().clean()
        if self.amount_limit is not None and self.amount_limit <= Decimal('0.00'):
            raise ValidationError({'amount_limit': 'Budget limit must be strictly greater than zero.'})

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({'end_date': 'End date cannot be prior to start date.'})

        if self.category:
            if self.user_id and self.category.user_id != self.user_id:
                raise ValidationError({'category': 'The selected category does not belong to your account.'})
            if self.category.category_type != 'expense':
                raise ValidationError({'category': 'Budgets can only be assigned to Expense categories.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_spent_amount(self):
        """Calculates actual expense spending within this budget's timeframe."""
        query = Transaction.objects.filter(
            user=self.user,
            transaction_type='expense',
            transaction_date__gte=self.start_date,
            transaction_date__lte=self.end_date
        )
        if self.category:
            query = query.filter(category=self.category)

        total = query.aggregate(total_spent=models.Sum('amount'))['total_spent']
        return total or Decimal('0.00')

    def get_remaining_amount(self):
        """Calculates remaining budget allowance."""
        spent = self.get_spent_amount()
        limit = Decimal(str(self.amount_limit)) if self.amount_limit is not None else Decimal('0.00')
        return limit - spent

    def get_percentage_spent(self):
        """Returns spent percentage relative to amount_limit."""
        limit = Decimal(str(self.amount_limit)) if self.amount_limit is not None else Decimal('0.00')
        if not limit or limit == Decimal('0.00'):
            return 0.0
        spent = self.get_spent_amount()
        ratio = (spent / limit) * Decimal('100.0')
        return round(float(ratio), 1)

    def get_status(self):
        """Returns budget alert status: normal (<80%), warning (80-99%), exceeded (>=100%)."""
        pct = self.get_percentage_spent()
        if pct >= 100.0:
            return 'exceeded'
        elif pct >= 80.0:
            return 'warning'
        return 'normal'

    def __str__(self):
        scope = self.category.name if self.category else "Overall"
        return f"{self.name} ({scope}) - Limit: ₹{self.amount_limit}"


class RecurringTransaction(models.Model):
    """
    Scheduled recurring transaction rules to automatically generate repetitive expenses or income.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_transactions')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='recurring_rules')
    transaction_type = models.CharField(max_length=10, choices=Transaction.TRANSACTION_TYPES, default='expense')
    title = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_method = models.CharField(max_length=20, choices=Transaction.PAYMENT_METHODS, default='bank_transfer')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    start_date = models.DateField(default=timezone.now)
    next_due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    last_generated_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Recurring Transaction Rule'
        verbose_name_plural = 'Recurring Transaction Rules'
        ordering = ['next_due_date']

    def __str__(self):
        freq_display = self.get_frequency_display() if hasattr(self, 'get_frequency_display') else self.frequency
        return f"{self.title} - {freq_display} (₹{self.amount})"


def create_default_categories_for_user(user):
    """
    Helper function to seed realistic, sensible starter categories for a newly registered user.
    """
    default_categories = [
        # Expense categories
        {'name': 'Food & Dining', 'category_type': 'expense', 'color': '#ef4444', 'icon': 'bi-egg-fried', 'description': 'Restaurants, takeout, and cafes'},
        {'name': 'Groceries', 'category_type': 'expense', 'color': '#f97316', 'icon': 'bi-basket2', 'description': 'Supermarket and daily household items'},
        {'name': 'Transportation', 'category_type': 'expense', 'color': '#06b6d4', 'icon': 'bi-car-front', 'description': 'Fuel, public transit, cab fares'},
        {'name': 'Housing & Rent', 'category_type': 'expense', 'color': '#8b5cf6', 'icon': 'bi-house-door', 'description': 'Apartment rent, maintenance, mortgage'},
        {'name': 'Utilities & Bills', 'category_type': 'expense', 'color': '#eab308', 'icon': 'bi-lightning-charge', 'description': 'Electricity, water, gas, Wi-Fi, mobile plans'},
        {'name': 'Shopping', 'category_type': 'expense', 'color': '#ec4899', 'icon': 'bi-bag', 'description': 'Apparel, gadgets, accessories'},
        {'name': 'Healthcare & Medical', 'category_type': 'expense', 'color': '#10b981', 'icon': 'bi-heart-pulse', 'description': 'Doctor visits, medicines, lab tests'},
        {'name': 'Entertainment', 'category_type': 'expense', 'color': '#6366f1', 'icon': 'bi-film', 'description': 'Movies, streaming services, events'},
        {'name': 'Education & Books', 'category_type': 'expense', 'color': '#3b82f6', 'icon': 'bi-book', 'description': 'Tuition, courses, books, learning tools'},
        {'name': 'Other Expense', 'category_type': 'expense', 'color': '#64748b', 'icon': 'bi-three-dots', 'description': 'Miscellaneous non-categorized spending'},
        
        # Income categories
        {'name': 'Salary', 'category_type': 'income', 'color': '#10b981', 'icon': 'bi-cash-stack', 'description': 'Monthly employment salary & wages'},
        {'name': 'Freelance & Consulting', 'category_type': 'income', 'color': '#3b82f6', 'icon': 'bi-laptop', 'description': 'Freelance projects and advisory fees'},
        {'name': 'Investments & Dividends', 'category_type': 'income', 'color': '#8b5cf6', 'icon': 'bi-graph-up-arrow', 'description': 'Stocks, mutual funds, interest, crypto'},
        {'name': 'Business', 'category_type': 'income', 'color': '#06b6d4', 'icon': 'bi-briefcase', 'description': 'Business revenue and client retainers'},
        {'name': 'Gifts & Grants', 'category_type': 'income', 'color': '#f59e0b', 'icon': 'bi-gift', 'description': 'Financial gifts, cashbacks, awards'},
        {'name': 'Other Income', 'category_type': 'income', 'color': '#64748b', 'icon': 'bi-wallet2', 'description': 'Miscellaneous earnings and refunds'},
    ]

    for item in default_categories:
        Category.objects.get_or_create(
            user=user,
            name=item['name'],
            category_type=item['category_type'],
            defaults={
                'color': item['color'],
                'icon': item['icon'],
                'description': item['description']
            }
        )
