from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.notifications import events
from .models import Expense, Settlement
from .serializers import ExpenseSerializer, SettlementSerializer

class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().order_by('-date', '-created_at')
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        group_id = self.request.query_params.get('group_id')
        if group_id:
            qs = qs.filter(group_id=group_id)
        return qs

    # actor_id = the logged-in user making the change; it decides who is NOT notified.
    # DELETE has no body, so it comes as ?actor_id= there.

    def perform_create(self, serializer):
        expense = serializer.save()
        actor = events.resolve_actor(self.request.data.get('actor_id')) or expense.created_by
        events.expense_added(expense, actor)

    def perform_update(self, serializer):
        before = events.snapshot_expense(serializer.instance)
        actor = events.resolve_actor(self.request.data.get('actor_id'))
        expense = serializer.save(updated_by=actor, updated_at=timezone.now())
        events.expense_edited(before, expense, actor)

    def perform_destroy(self, instance):
        before = events.snapshot_expense(instance)
        actor = events.resolve_actor(self.request.query_params.get('actor_id'))
        instance.delete()
        events.expense_deleted(before, actor)

class SettlementViewSet(viewsets.ModelViewSet):
    queryset = Settlement.objects.all().order_by('-date', '-created_at')
    serializer_class = SettlementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        group_id = self.request.query_params.get('group_id')
        if group_id:
            qs = qs.filter(group_id=group_id)
        return qs

    def perform_create(self, serializer):
        actor = events.resolve_actor(self.request.data.get('actor_id'))
        settlement = serializer.save(created_by=actor)
        events.settlement_recorded(settlement, actor)

    def perform_destroy(self, instance):
        before = events.snapshot_settlement(instance)
        actor = events.resolve_actor(self.request.query_params.get('actor_id'))
        instance.delete()
        events.settlement_deleted(before, actor)
