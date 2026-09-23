from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Group, GroupMember
from .serializers import GroupSerializer
from apps.users.models import UserProfile
from apps.notifications import activity
from apps.notifications.events import resolve_actor
from domain.balance_engine import calculate_group_balances
from domain.debt_simplifier import simplify_debts

class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().order_by('-created_at')
    serializer_class = GroupSerializer

    def list(self, request, *args, **kwargs):
        # Ensure default users exist
        if not UserProfile.objects.filter(username='venkatesh').exists():
            demo_users = [
                {"username": "venkatesh", "name": "Venkatesh", "email": "venkatesh@example.com", "phone_number": "6382247549", "password": "10", "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Venkatesh"},
                {"username": "alex", "name": "Alex Johnson", "email": "alex@example.com", "phone_number": "9876543210", "password": "10", "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Alex"},
                {"username": "sarah", "name": "Sarah Miller", "email": "sarah@example.com", "phone_number": "9876543211", "password": "10", "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah"},
                {"username": "david", "name": "David Chen", "email": "david@example.com", "phone_number": "9876543212", "password": "10", "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=David"},
            ]
            for u in demo_users:
                UserProfile.objects.get_or_create(username=u["username"], defaults=u)

        # Auto-seed Groceries 🛒 group if none exist
        if not Group.objects.filter(name__icontains='groceries').exists():
            users = list(UserProfile.objects.all())
            groceries_group = Group.objects.create(
                name="Groceries 🛒",
                description="Shared household groceries, food items, and quick-commerce orders.",
                category="HOME",
                currency="₹"
            )
            for u in users:
                GroupMember.objects.create(group=groceries_group, user=u)

        response = super().list(request, *args, **kwargs)

        # ?user_id= asks "how much has this person not seen in each group?"
        viewer = resolve_actor(request.query_params.get('user_id'))
        if viewer:
            for group in response.data:
                group['unseen_count'] = activity.unseen_count(group['id'], viewer.id)
        return response

    def retrieve(self, request, *args, **kwargs):
        group = self.get_object()
        serializer = self.get_serializer(group)
        data = serializer.data

        from apps.expenses.models import Expense, Settlement
        from apps.expenses.serializers import ExpenseSerializer, SettlementSerializer

        expenses = Expense.objects.filter(group=group).order_by('-date', '-created_at')
        settlements = Settlement.objects.filter(group=group).order_by('-date', '-created_at')

        exp_data_for_engine = []
        for e in expenses:
            exp_data_for_engine.append({
                "payers": [{"user_id": p.user.id, "amount": float(p.amount_paid)} for p in e.payers.all()],
                "shares": [{"user_id": s.user.id, "amount": float(s.amount_owed)} for s in e.shares.all()]
            })

        st_data_for_engine = []
        for st in settlements:
            st_data_for_engine.append({
                "payer_id": st.payer.id,
                "payee_id": st.payee.id,
                "amount": float(st.amount)
            })

        member_ids = [m.id for m in group.members.all()]
        calc_result = calculate_group_balances(member_ids, exp_data_for_engine, st_data_for_engine)
        
        net_balances = calc_result["net_balances"]
        simplified_debts = simplify_debts(net_balances)

        data["total_spending"] = calc_result["total_group_spending"]
        data["net_balances"] = net_balances
        data["simplified_debts"] = simplified_debts
        data["expenses"] = ExpenseSerializer(expenses, many=True).data
        data["settlements"] = SettlementSerializer(settlements, many=True).data

        viewer = resolve_actor(request.query_params.get('user_id'))
        if viewer:
            baseline = activity.baseline_for(group.id, viewer.id)
            data["last_seen_at"] = baseline
            data["activity"] = activity.serialize(activity.for_user(group.id, viewer.id), viewer.id)
            data["unseen_count"] = activity.unseen_count(group.id, viewer.id)

        return Response(data)

    @action(detail=True, methods=['post'])
    def seen(self, request, pk=None):
        """Mark this group as looked at. Returns the previous mark so the page can keep
        highlighting what was new for the rest of the visit."""
        group = self.get_object()
        viewer = resolve_actor(request.data.get('user_id'))
        if not viewer:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        previous = activity.mark_seen(group.id, viewer.id)
        if previous is None:
            return Response({'error': 'That user is not in this group'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'previous_seen_at': previous, 'unseen_count': 0})

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        group = self.get_object()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = UserProfile.objects.get(id=user_id)
        except UserProfile.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        member, created = GroupMember.objects.get_or_create(group=group, user=user)
        if not created:
            return Response({'message': 'User is already a member of this group'}, status=status.HTTP_200_OK)

        return Response({'message': f'Added {user.name} to {group.name}'}, status=status.HTTP_201_CREATED)
