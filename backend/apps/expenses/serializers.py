import json
from django.db import transaction
from rest_framework import serializers
from .models import Expense, ExpensePayer, ExpenseShare, Settlement
from apps.users.serializers import UserProfileSerializer
from apps.users.models import UserProfile
from apps.groups.models import Group
from domain.split_calculator import calculate_splits, SplitType

class ExpensePayerSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all(), source='user'
    )

    class Meta:
        model = ExpensePayer
        fields = ['id', 'user', 'user_id', 'amount_paid']

class ExpenseShareSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all(), source='user'
    )
    amount_owed = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0.0)
    percentage = serializers.FloatField(required=False, default=0.0)

    class Meta:
        model = ExpenseShare
        fields = ['id', 'user', 'user_id', 'amount_owed', 'percentage']

class SettlementSerializer(serializers.ModelSerializer):
    payer = UserProfileSerializer(read_only=True)
    payee = UserProfileSerializer(read_only=True)
    payer_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all(), source='payer'
    )
    payee_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all(), source='payee'
    )
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), source='group'
    )
    created_by = UserProfileSerializer(read_only=True)

    class Meta:
        model = Settlement
        fields = ['id', 'group_id', 'payer', 'payer_id', 'payee', 'payee_id', 'amount', 'date', 'notes', 'created_by', 'created_at']

class ExpenseSerializer(serializers.ModelSerializer):
    payers = ExpensePayerSerializer(many=True, required=True)
    shares = ExpenseShareSerializer(many=True, required=False)
    created_by = UserProfileSerializer(read_only=True)
    created_by_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all(), source='created_by', required=False, allow_null=True
    )
    updated_by = UserProfileSerializer(read_only=True)
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), source='group'
    )

    class Meta:
        model = Expense
        fields = [
            'id', 'group_id', 'description', 'amount', 'category', 
            'split_type', 'created_by', 'created_by_id', 'notes', 'date', 'created_at',
            'updated_by', 'updated_at', 'payers', 'shares'
        ]
        read_only_fields = ['updated_at']

    def _calculate_owed(self, amount, split_type, payers_data, shares_data):
        total_amount = float(amount)

        total_paid = sum(float(p['amount_paid']) for p in payers_data)
        if abs(total_paid - total_amount) > 0.01:
            raise serializers.ValidationError(
                f"Total amount paid (${total_paid:.2f}) does not match expense amount (${total_amount:.2f})."
            )

        participant_ids = [s['user'].id for s in shares_data] if shares_data else []
        custom_vals = {}
        
        if split_type == SplitType.EXACT:
            custom_vals = {s['user'].id: float(s.get('amount_owed', 0.0)) for s in shares_data}
        elif split_type == SplitType.PERCENTAGE:
            custom_vals = {s['user'].id: float(s.get('percentage', 0.0)) for s in shares_data}

        owed_map, error_msg = calculate_splits(total_amount, split_type, participant_ids, custom_vals)
        if error_msg:
            raise serializers.ValidationError(error_msg)
        return owed_map

    def _write_payers_and_shares(self, expense, payers_data, shares_data, owed_map):
        for p in payers_data:
            ExpensePayer.objects.create(
                expense=expense,
                user=p['user'],
                amount_paid=p['amount_paid']
            )

        for s in shares_data:
            uid = s['user'].id
            ExpenseShare.objects.create(
                expense=expense,
                user=s['user'],
                amount_owed=owed_map.get(uid, 0.0),
                percentage=s.get('percentage', 0.0)
            )

    def create(self, validated_data):
        payers_data = validated_data.pop('payers', [])
        shares_data = validated_data.pop('shares', [])
        split_type = validated_data.get('split_type', SplitType.EQUAL)

        owed_map = self._calculate_owed(validated_data.get('amount'), split_type, payers_data, shares_data)

        expense = Expense.objects.create(**validated_data)
        self._write_payers_and_shares(expense, payers_data, shares_data, owed_map)
        return expense

    def update(self, instance, validated_data):
        try:
            platform = json.loads(instance.notes or '').get('platform')
        except (ValueError, AttributeError):
            platform = None
        if platform:
            raise serializers.ValidationError(
                f"This is a {platform} order split. Re-split it from Quick Grocery Apps instead."
            )

        payers_data = validated_data.pop('payers', None)
        shares_data = validated_data.pop('shares', None)
        if payers_data is None or shares_data is None:
            raise serializers.ValidationError("payers and shares are required when editing an expense.")
        validated_data.pop('created_by', None)  # the original author stays the author

        owed_map = self._calculate_owed(
            validated_data.get('amount', instance.amount),
            validated_data.get('split_type', instance.split_type),
            payers_data,
            shares_data,
        )

        with transaction.atomic():
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            instance.payers.all().delete()
            instance.shares.all().delete()
            self._write_payers_and_shares(instance, payers_data, shares_data, owed_map)
        return instance
