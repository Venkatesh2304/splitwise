from rest_framework import serializers
from .models import UserProfile
from .phone import normalize_phone

class UserProfileSerializer(serializers.ModelSerializer):
    # Whether this person can be paid, without handing their UPI id to every caller
    has_upi = serializers.SerializerMethodField()
    upi_id = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'name', 'email', 'phone_number', 'avatar_url', 'has_upi', 'upi_id', 'created_at']

    def get_has_upi(self, user):
        return bool(user.upi_id)

    def validate_phone_number(self, value):
        if not value:
            return ''
        phone = normalize_phone(value)
        if not phone:
            raise serializers.ValidationError("Enter a 10-digit mobile number.")
        return phone
