"""
Django Forms for SpendWise application.
Includes user registration, profile editing, transaction management, category management, and budget management.
"""

from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Budget,
    Category,
    Transaction,
    UserProfile,
    create_default_categories_for_user,
)


class UserRegistrationForm(forms.ModelForm):
    """
    User registration form with secure password confirmation and account initialization.
    """
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'First Name'
    }))
    last_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Last Name'
    }))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Email Address'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Password (min. 8 characters)'
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Confirm Password'
    }))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken. Please choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        if password and len(password) < 8:
            self.add_error('password', "Password must be at least 8 characters long.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            # Initialize default categories and user profile
            UserProfile.objects.get_or_create(user=user)
            create_default_categories_for_user(user)
        return user


class UserProfileForm(forms.ModelForm):
    """
    Profile information update form.
    """
    first_name = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = UserProfile
        fields = ['phone', 'currency', 'bio', 'avatar']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 9876543210'}),
            'currency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'INR'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short financial bio or notes'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.user and User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("This email is already in use by another account.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data.get('first_name', '')
            self.user.last_name = self.cleaned_data.get('last_name', '')
            self.user.email = self.cleaned_data.get('email', '')
            if commit:
                self.user.save()
        if commit:
            profile.save()
        return profile


class CategoryForm(forms.ModelForm):
    """
    Category creation and update form.
    """
    class Meta:
        model = Category
        fields = ['name', 'category_type', 'color', 'icon', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Groceries, Freelance'}),
            'category_type': forms.Select(attrs={'class': 'form-select'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bi-tag'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Brief description'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        category_type = self.cleaned_data.get('category_type')
        if self.user and name and category_type:
            qs = Category.objects.filter(user=self.user, name__iexact=name, category_type=category_type)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(f"A {category_type} category with this name already exists in your account.")
        return name

    def save(self, commit=True):
        category = super().save(commit=False)
        if self.user:
            category.user = self.user
        if commit:
            category.save()
        return category


class TransactionForm(forms.ModelForm):
    """
    Transaction creation and update form with strict user-scoping.
    """
    class Meta:
        model = Transaction
        fields = [
            'title',
            'amount',
            'transaction_type',
            'category',
            'transaction_date',
            'payment_method',
            'reference_number',
            'description'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Monthly Grocery Restock'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_transaction_type'}),
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'id_category'}),
            'transaction_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional reference/UTR/invoice'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Additional notes'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            if not self.instance.pk and not getattr(self.instance, 'user_id', None):
                self.instance.user = self.user
            self.fields['category'].queryset = Category.objects.filter(user=self.user)
            self.fields['category'].empty_label = "-- Select Category --"
        if not self.instance.pk and 'transaction_date' in self.fields:
            self.fields['transaction_date'].initial = timezone.now().date()

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= Decimal('0.00'):
            raise ValidationError("Transaction amount must be strictly greater than zero.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        transaction_type = cleaned_data.get('transaction_type')

        if category and self.user and category.user_id != self.user.id:
            self.add_error('category', "The selected category does not belong to your account.")

        if category and transaction_type and category.category_type != transaction_type:
            self.add_error('category', f"Category '{category.name}' is designated for {category.get_category_type_display()}, not {transaction_type.capitalize()}.")

        return cleaned_data

    def save(self, commit=True):
        transaction = super().save(commit=False)
        if self.user:
            transaction.user = self.user
        if commit:
            transaction.save()
        return transaction


class BudgetForm(forms.ModelForm):
    """
    Budget creation and update form.
    """
    class Meta:
        model = Budget
        fields = ['name', 'category', 'amount_limit', 'period', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. October Total Budget'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            if not self.instance.pk and not getattr(self.instance, 'user_id', None):
                self.instance.user = self.user
            self.fields['category'].queryset = Category.objects.filter(user=self.user, category_type='expense')
            self.fields['category'].empty_label = "-- Overall (All Expense Categories) --"
            self.fields['category'].required = False

    def clean_amount_limit(self):
        amount = self.cleaned_data.get('amount_limit')
        if amount is not None and amount <= Decimal('0.00'):
            raise ValidationError("Budget limit must be strictly greater than zero.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        category = cleaned_data.get('category')

        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', "End date cannot be prior to start date.")

        if category and self.user and category.user_id != self.user.id:
            self.add_error('category', "The selected category does not belong to your account.")

        return cleaned_data

    def save(self, commit=True):
        budget = super().save(commit=False)
        if self.user:
            budget.user = self.user
        if commit:
            budget.save()
        return budget
