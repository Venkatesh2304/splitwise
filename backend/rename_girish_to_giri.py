import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'splitwise_backend.settings')
django.setup()

from apps.users.models import UserProfile

def run():
    girish = UserProfile.objects.filter(username__in=["girish", "giri"]).first()
    if girish:
        girish.name = "Giri"
        girish.username = "giri"
        girish.email = "giri@example.com"
        girish.save()
        print(f"Renamed user profile: ID={girish.id}, Name={girish.name}, Username={girish.username}, Phone={girish.phone_number}")
    else:
        giri = UserProfile.objects.create(
            name="Giri",
            username="giri",
            phone_number="9999900000",
            email="giri@example.com"
        )
        print(f"Created user profile: ID={giri.id}, Name={giri.name}, Username={giri.username}")

if __name__ == "__main__":
    run()
