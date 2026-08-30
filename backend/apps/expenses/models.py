import datetime
from django.db import models
from apps.users.models import UserProfile
from apps.groups.models import Group
from domain.split_calculator import SplitType

class ExpenseCategory(models.TextChoices):
    FOOD = 'FOOD', 'Food & Dining'
    UTILITIES = 'UTILITIES', 'Utilities & Bills'
    TRANSPORT = 'TRANSPORT', 'Transportation'
    ENTERTAINMENT = 'ENTERTAINMENT', 'Entertainment'
    SHOPPING = 'SHOPPING', 'Shopping'
    OTHER = 'OTHER', 'Other'

class Expense(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=30, choices=ExpenseCategory.choices, default=ExpenseCategory.OTHER)
    split_type = models.CharField(max_length=20, default=SplitType.EQUAL)
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='created_expenses')
    notes = models.TextField(blank=True, default='')
    date = models.DateField(default=datetime.date.today)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} (${self.amount})"

class ExpensePayer(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='payers')
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('expense', 'user')

    def __str__(self):
        return f"{self.user.name} paid ${self.amount_paid} for {self.expense.description}"

class ExpenseShare(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    amount_owed = models.DecimalField(max_digits=12, decimal_places=2)
    percentage = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('expense', 'user')

    def __str__(self):
        return f"{self.user.name} owes ${self.amount_owed} for {self.expense.description}"

class Settlement(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='settlements')
    payer = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='settlements_made')
    payee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='settlements_received')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=datetime.date.today)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payer.name} paid {self.payee.name} ${self.amount}"
