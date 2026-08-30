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

    class Meta:
        model = Settlement
        fields = ['id', 'group_id', 'payer', 'payer_id', 'payee', 'payee_id', 'amount', 'date', 'notes', 'created_at']

class ExpenseSerializer(serializers.ModelSerializer):
    payers = ExpensePayerSerializer(many=True, required=True)
    shares = ExpenseShareSerializer(many=True, required=False)
    created_by = UserProfileSerializer(read_only=True)
    created_by_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all(), source='created_by', required=False, allow_null=True
    )
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), source='group'
    )

    class Meta:
        model = Expense
        fields = [
            'id', 'group_id', 'description', 'amount', 'category', 
            'split_type', 'created_by', 'created_by_id', 'notes', 'date', 'created_at',
            'payers', 'shares'
        ]

    def create(self, validated_data):
        payers_data = validated_data.pop('payers', [])
        shares_data = validated_data.pop('shares', [])
        split_type = validated_data.get('split_type', SplitType.EQUAL)
        total_amount = float(validated_data.get('amount'))

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

        expense = Expense.objects.create(**validated_data)

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

        return expense
