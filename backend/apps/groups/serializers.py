from rest_framework import serializers
from .models import Group, GroupMember
from apps.users.serializers import UserProfileSerializer
from apps.users.models import UserProfile

class GroupMemberSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all(), source='user', write_only=True
    )

    class Meta:
        model = GroupMember
        fields = ['id', 'user', 'user_id', 'joined_at', 'is_active']

class GroupSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    member_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    total_spending = serializers.FloatField(read_only=True, default=0.0)

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'description', 'category', 'currency', 
            'created_at', 'members', 'member_ids', 'total_spending'
        ]

    def get_members(self, obj):
        memberships = GroupMember.objects.filter(group=obj).select_related('user')
        result = []
        for gm in memberships:
            user_data = UserProfileSerializer(gm.user).data
            user_data['is_active'] = getattr(gm, 'is_active', True)
            result.append(user_data)
        return result

    def create(self, validated_data):
        member_ids = validated_data.pop('member_ids', [])
        group = Group.objects.create(**validated_data)
        
        if member_ids:
            users = UserProfile.objects.filter(id__in=member_ids)
            for u in users:
                GroupMember.objects.create(group=group, user=u)
        
        return group
