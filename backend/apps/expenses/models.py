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

class GroceryOrderRecord(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='grocery_orders')
    platform = models.CharField(max_length=50) # 'SWIGGY_INSTAMART', 'BLINKIT', etc.
    order_id = models.CharField(max_length=100)
    placed_at = models.CharField(max_length=100, blank=True, default='')
    total_amount = models.FloatField(default=0.0)
    other_charges = models.FloatField(default=0.0)
    product_names = models.JSONField(default=list)
    item_details = models.JSONField(default=list)
    raw_payload = models.JSONField(default=dict, blank=True)
    full_order_json = models.JSONField(default=dict, blank=True) # Full raw order JSON payload
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'platform', 'order_id')
        ordering = ['-created_at', '-id']

    def to_dict(self):
        item_objs = self.items.all()
        if item_objs.exists():
            prods = [it.name for it in item_objs]
            details = [{"name": it.name, "price": float(it.price), "quantity": it.quantity} for it in item_objs]
        else:
            prods = self.product_names or []
            details = self.item_details or []

        return {
            "order_id": self.order_id,
            "order_type": self.platform,
            "placed_at": self.placed_at,
            "total_amount": float(self.total_amount),
            "product_names": prods,
            "item_details": details,
            "other_charges": float(self.other_charges),
            "full_order_json": self.full_order_json or self.raw_payload or {}
        }

    def __str__(self):
        return f"[{self.platform}] Order #{self.order_id} - ₹{self.total_amount} ({self.user.name})"

class GroceryOrderItem(models.Model):
    order = models.ForeignKey(GroceryOrderRecord, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=255)
    price = models.FloatField(default=0.0)
    quantity = models.IntegerField(default=1)
    item_json = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} (x{self.quantity}) - ₹{self.price}"


