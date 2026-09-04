import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'splitwise_backend.settings')
django.setup()

from apps.users.models import UserProfile
from apps.groups.models import Group
from apps.expenses.models import Expense, ExpensePayer, ExpenseShare, GroceryOrderRecord, GroceryOrderItem
from apps.expenses.grocery_engine import state

def run():
    print("=== RESETTING DB ENTRIES (KEEPING USERS, TOKENS & NUMBERS) ===")

    # 1. Clear expenses and order records
    shares_cnt, _ = ExpenseShare.objects.all().delete()
    payers_cnt, _ = ExpensePayer.objects.all().delete()
    exp_cnt, _ = Expense.objects.all().delete()
    items_cnt, _ = GroceryOrderItem.objects.all().delete()
    records_cnt, _ = GroceryOrderRecord.objects.all().delete()

    print(f"Deleted {exp_cnt} Expenses, {shares_cnt} ExpenseShares, {payers_cnt} ExpensePayers.")
    print(f"Deleted {records_cnt} GroceryOrderRecords, {items_cnt} GroceryOrderItems.")

    # 2. Add user Giri with dummy number
    giri, created = UserProfile.objects.get_or_create(
        username="giri",
        defaults={
            "name": "Giri",
            "phone_number": "9999900000",
            "email": "giri@example.com"
        }
    )
    if created:
        print(f"Created new user profile: Giri (ID={giri.id}, Phone={giri.phone_number})")
    else:
        print(f"User profile Giri already exists (ID={giri.id}, Phone={giri.phone_number})")

    # Add Giri to all groups
    groups = Group.objects.all()
    for g in groups:
        g.members.add(giri)
        print(f"Added Giri to group '{g.name}' (Total members: {g.members.count()})")

    # 3. Clear in-memory order caches
    state.BLINKIT_ORDER_CACHES.clear()
    state.SWIGGY_ORDER_CACHES.clear()
    print("Cleared in-memory order caches.")

    # 4. Summary of current users
    print("\n--- ACTIVE USER PROFILES IN DATABASE ---")
    for u in UserProfile.objects.all():
        b_tok = f"Active ({u.blinkit_access_token[:12]}...)" if u.blinkit_access_token else "None"
        s_tok = f"Active ({u.swiggy_access_token[:12]}...)" if u.swiggy_access_token else "None"
        print(f"ID={u.id} | Name={u.name} | Phone={u.phone_number} | Blinkit={b_tok} | Swiggy={s_tok}")

    print("\n✅ DB RESET COMPLETE & GIRISH ADDED SUCCESSFULLY!")

if __name__ == "__main__":
    run()
