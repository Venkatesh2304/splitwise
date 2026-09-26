from rest_framework import serializers
from .models import UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    # Whether this person can be paid, without handing their UPI id to every caller
    has_upi = serializers.SerializerMethodField()
    upi_id = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'name', 'email', 'phone_number', 'avatar_url', 'has_upi', 'upi_id', 'created_at']

    def get_has_upi(self, user):
        return bool(user.upi_id)
