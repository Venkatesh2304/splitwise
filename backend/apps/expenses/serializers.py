import json
from django.db import transaction
from rest_framework import serializers
from .models import Expense, ExpensePayer, ExpenseShare, Settlement
from apps.users.serializers import UserProfileSerializer
from apps.users.models import UserProfile
from apps.groups.models import Group
from domain.split_calculator import calculate_splits, SplitType
from .itemized import ALL, SPECIFIC, split_items

# A bill typed in line by line, each item charged to the people who had it
ITEMS = 'ITEMS'

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
    # [{name, price, assigned_member_ids}] when split_type is ITEMS; stored in notes
    items = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), source='group'
    )

    class Meta:
        model = Expense
        fields = [
            'id', 'group_id', 'description', 'amount', 'category', 
            'split_type', 'created_by', 'created_by_id', 'notes', 'date', 'created_at',
            'updated_by', 'updated_at', 'payers', 'shares', 'items'
        ]
        read_only_fields = ['updated_at']

    def _normalise_items(self, raw_items, group, amount):
        """Check the typed-in items and put them in the shape stored in notes."""
        members = list(group.members.all())
        member_ids = [m.id for m in members]
        first_names = {m.id: m.name.split(' ')[0] for m in members}

        if not raw_items:
            raise serializers.ValidationError("Add at least one item, or split the expense another way.")

        normalised = []
        items_total = 0.0
        for raw in raw_items:
            name = str(raw.get('name') or '').strip() or 'Item'
            try:
                price = round(float(raw.get('price') or 0.0), 2)
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"“{name}” needs a number for its price.")
            if price < 0:
                raise serializers.ValidationError(f"“{name}” can't cost less than nothing.")

            try:
                assigned = [int(uid) for uid in (raw.get('assigned_member_ids') or [])]
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"“{name}” has an unreadable list of people.")
            outsiders = [uid for uid in assigned if uid not in member_ids]
            if outsiders:
                raise serializers.ValidationError(f"“{name}” is assigned to someone who isn't in this group.")
            if not assigned:
                raise serializers.ValidationError(f"“{name}” isn't assigned to anyone — tap at least one person.")

            items_total += price
            normalised.append({
                "name": name,
                "price": price,
                "split_type": ALL if set(assigned) == set(member_ids) else SPECIFIC,
                "assigned_member_ids": assigned,
                "assigned_names": [first_names[uid] for uid in assigned],
            })

        if round(items_total, 2) > float(amount) + 0.01:
            raise serializers.ValidationError(
                f"The items come to {items_total:.2f}, which is more than the expense's {float(amount):.2f}."
            )
        return normalised, member_ids, members

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

    def _prepare_itemised(self, validated_data, payers_data, raw_items):
        """Shares come from the items, not from what the client sent as shares."""
        group = validated_data['group']
        amount = validated_data.get('amount')
        items, member_ids, members = self._normalise_items(raw_items, group, amount)

        payer_id = payers_data[0]['user'].id if payers_data else member_ids[0]
        owed_map = split_items(float(amount), items, member_ids, payer_id)
        shares_data = [{'user': member} for member in members]

        # The same shape a grocery order writes, minus "platform" — that key is what marks
        # an expense as belonging to Blinkit/Swiggy, and this one is hand-entered
        validated_data['notes'] = json.dumps({"split_mode": "ITEMIZED", "items": items})
        return owed_map, shares_data

    def create(self, validated_data):
        payers_data = validated_data.pop('payers', [])
        shares_data = validated_data.pop('shares', [])
        raw_items = validated_data.pop('items', None)
        split_type = validated_data.get('split_type', SplitType.EQUAL)

        if split_type == ITEMS:
            owed_map, shares_data = self._prepare_itemised(validated_data, payers_data, raw_items)
        else:
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
        raw_items = validated_data.pop('items', None)
        if payers_data is None or shares_data is None:
            raise serializers.ValidationError("payers and shares are required when editing an expense.")
        validated_data.pop('created_by', None)  # the original author stays the author

        split_type = validated_data.get('split_type', instance.split_type)
        if split_type == ITEMS:
            validated_data.setdefault('group', instance.group)
            validated_data.setdefault('amount', instance.amount)
            owed_map, shares_data = self._prepare_itemised(validated_data, payers_data, raw_items)
        else:
            owed_map = self._calculate_owed(
                validated_data.get('amount', instance.amount),
                split_type,
                payers_data,
                shares_data,
            )
            # Was itemised, isn't any more: the stored items no longer describe it
            if instance.split_type == ITEMS:
                validated_data['notes'] = ''

        with transaction.atomic():
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            instance.payers.all().delete()
            instance.shares.all().delete()
            self._write_payers_and_shares(instance, payers_data, shares_data, owed_map)
        return instance
