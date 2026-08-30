from django.core.management.base import BaseCommand
from apps.users.models import UserProfile
from apps.groups.models import Group

class Command(BaseCommand):
    help = "Seeds initial 5 users with phone numbers and DB-stored platform tokens, and adds them to Groceries group."

    def handle(self, *args, **options):
        initial_users_data = [
            {"username": "venkatesh", "name": "Venkatesh", "phone_number": "6382247549", "email": "venkatesh@example.com"},
            {"username": "rahul", "name": "Rahul", "phone_number": "9876543210", "email": "rahul@example.com"},
            {"username": "akash", "name": "Akash", "phone_number": "9876543211", "email": "akash@example.com"},
            {"username": "anish", "name": "Anish", "phone_number": "9876543212", "email": "anish@example.com"},
            {"username": "aathesh", "name": "Aathesh", "phone_number": "9965817968", "email": "aathesh@example.com"},
        ]

        UserProfile.objects.filter(username="aatesh").delete()

        created_users = []
        for user_data in initial_users_data:
            user, created = UserProfile.objects.get_or_create(
                username=user_data["username"],
                defaults={
                    "name": user_data["name"],
                    "phone_number": user_data["phone_number"],
                    "email": user_data["email"],
                    "password": "10",
                    "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_data['name']}"
                }
            )
            if not created:
                user.name = user_data["name"]
                user.phone_number = user_data["phone_number"]
                user.password = "10"
                user.save()
            
            status_str = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"User '{user.name}' ({user.username}) -> Phone: {user.phone_number} [{status_str}]"))
            created_users.append(user)

        # Seed per-user platform tokens directly in Django DB
        venkat = UserProfile.objects.filter(username="venkatesh").first()
        if venkat:
            venkat.blinkit_access_token = "v2::41bccbe5-8c91-430f-8ed0-04decc5924eb"
            venkat.blinkit_auth_key = "c761ec3633c22afad934fb17a66385c1c06c5472b4898b866b7306186d0bb477"
            venkat.blinkit_device_id = "5f2a83a6911b4f8b"
            venkat.blinkit_session_uuid = "d1e49859-cb40-4f0a-8110-c213f22a718a"
            venkat.save()

        aathesh = UserProfile.objects.filter(username="aathesh").first()
        if aathesh:
            aathesh.blinkit_access_token = "v2::89a1cce4-9b22-4411-9ff1-12cdeaa558ab"
            aathesh.blinkit_auth_key = "c761ec3633c22afad934fb17a66385c1c06c5472b4898b866b7306186d0bb477"
            aathesh.blinkit_device_id = "8a3b91c742019e1f"
            aathesh.blinkit_session_uuid = "e2f58912-ab50-4d1b-9221-d324911b829b"
            aathesh.save()

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
                f"Successfully updated group '{groceries_group.name}' with DB-mapped platform tokens for all {len(created_users)} users."
            )
        )
