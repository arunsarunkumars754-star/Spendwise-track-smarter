"""
Django REST Framework serializers for SpendWise.
Provides user-scoped serialization, nested representations, and ownership validation.
"""

from decimal import Decimal

from rest_framework import serializers

from .models import Budget, Category, Transaction


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for user categories with transaction count property.
    """
    transaction_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'category_type',
            'description',
            'color',
            'icon',
            'transaction_count',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_name(self, value):
        user = self.context['request'].user
        category_type = self.initial_data.get('category_type') or (self.instance.category_type if self.instance else 'expense')
        
        qs = Category.objects.filter(user=user, name__iexact=value.strip(), category_type=category_type)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
            
        if qs.exists():
            raise serializers.ValidationError(f"A {category_type} category with this name already exists in your account.")
        return value.strip()


class TransactionCategorySummarySerializer(serializers.ModelSerializer):
    """Nested category representation for transaction payloads."""
    class Meta:
        model = Category
        fields = ['id', 'name', 'category_type', 'color', 'icon']


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for financial transactions with comprehensive validation.
    """
    category_details = TransactionCategorySummarySerializer(source='category', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id',
            'title',
            'amount',
            'transaction_type',
            'category',
            'category_details',
            'transaction_date',
            'payment_method',
            'reference_number',
            'description',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_amount(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Amount must be strictly greater than zero.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        category = attrs.get('category') or (self.instance.category if self.instance else None)
        tx_type = attrs.get('transaction_type') or (self.instance.transaction_type if self.instance else None)

        if category and category.user_id != user.id:
            raise serializers.ValidationError({'category': "The selected category does not belong to your account."})

        if category and tx_type and category.category_type != tx_type:
            raise serializers.ValidationError({
                'category': f"Category type '{category.category_type}' does not match transaction type '{tx_type}'."
            })

        return attrs


class BudgetSerializer(serializers.ModelSerializer):
    """
    Serializer for budget limits with dynamic spending calculation.
    """
    category_details = TransactionCategorySummarySerializer(source='category', read_only=True)
    spent_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    percentage_spent = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            'id',
            'name',
            'category',
            'category_details',
            'amount_limit',
            'period',
            'start_date',
            'end_date',
            'spent_amount',
            'remaining_amount',
            'percentage_spent',
            'status',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'spent_amount', 'remaining_amount', 'percentage_spent', 'status']

    def get_spent_amount(self, obj):
        return float(obj.get_spent_amount())

    def get_remaining_amount(self, obj):
        return float(obj.get_remaining_amount())

    def get_percentage_spent(self, obj):
        return obj.get_percentage_spent()

    def get_status(self, obj):
        return obj.get_status()

    def validate_amount_limit(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Budget limit must be strictly greater than zero.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        start_date = attrs.get('start_date') or (self.instance.start_date if self.instance else None)
        end_date = attrs.get('end_date') or (self.instance.end_date if self.instance else None)
        category = attrs.get('category') or (self.instance.category if self.instance else None)

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({'end_date': "End date cannot be prior to start date."})

        if category:
            if category.user_id != user.id:
                raise serializers.ValidationError({'category': "The selected category does not belong to your account."})
            if category.category_type != 'expense':
                raise serializers.ValidationError({'category': "Budgets can only be assigned to Expense categories."})

        return attrs
