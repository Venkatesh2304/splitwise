from django.core.management.base import BaseCommand
from apps.users.models import UserProfile
from apps.groups.models import Group

class Command(BaseCommand):
    help = "Seeds initial 5 users (venkatesh, rahul, akash, anish, aatesh) and adds them to the default Groceries group."

    def handle(self, *args, **options):
        initial_users_data = [
            {"username": "venkatesh", "name": "Venkatesh", "email": "venkatesh@example.com"},
            {"username": "rahul", "name": "Rahul", "email": "rahul@example.com"},
            {"username": "akash", "name": "Akash", "email": "akash@example.com"},
            {"username": "anish", "name": "Anish", "email": "anish@example.com"},
            {"username": "aatesh", "name": "Aatesh", "email": "aatesh@example.com"},
        ]

        created_users = []
        for user_data in initial_users_data:
            user, created = UserProfile.objects.get_or_create(
                username=user_data["username"],
                defaults={
                    "name": user_data["name"],
                    "email": user_data["email"],
                    "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_data['name']}"
                }
            )
            if not created and user.name != user_data["name"]:
                user.name = user_data["name"]
                user.save()
            
            status_str = "Created" if created else "Exists"
            self.stdout.write(self.style.SUCCESS(f"User '{user.name}' ({user.username}) -> {status_str}"))
            created_users.append(user)

        # Get or create the main Groceries group
        groceries_group, group_created = Group.objects.get_or_create(
            name="Groceries 🛒",
            defaults={
                "description": "Shared grocery expenses and quick commerce orders (Blinkit / Swiggy Instamart)",
                "category": "GROCERIES",
                "currency": "₹"
            }
        )

        for user in created_users:
            if user not in groceries_group.members.all():
                groceries_group.members.add(user)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated group '{groceries_group.name}' with all {len(created_users)} users."
            )
        )
