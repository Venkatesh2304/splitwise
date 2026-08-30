from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import UserProfile
from .serializers import UserProfileSerializer

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all().order_by('id')
    serializer_class = UserProfileSerializer

    def list(self, request, *args, **kwargs):
        # Auto-seed initial demo users including venkatesh if none exist
        if not UserProfile.objects.filter(username='venkatesh').exists():
            demo_users = [
                {
                    "username": "venkatesh",
                    "name": "Venkatesh",
                    "email": "venkatesh@example.com",
                    "phone_number": "6382247549",
                    "password": "10",
                    "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Venkatesh"
                },
                {
                    "username": "alex",
                    "name": "Alex Johnson",
                    "email": "alex@example.com",
                    "phone_number": "9876543210",
                    "password": "10",
                    "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Alex"
                },
                {
                    "username": "sarah",
                    "name": "Sarah Miller",
                    "email": "sarah@example.com",
                    "phone_number": "9876543211",
                    "password": "10",
                    "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah"
                },
                {
                    "username": "david",
                    "name": "David Chen",
                    "email": "david@example.com",
                    "phone_number": "9876543212",
                    "password": "10",
                    "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=David"
                },
            ]
            for u in demo_users:
                UserProfile.objects.get_or_create(username=u["username"], defaults=u)
        
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def login(self, request):
        username = request.data.get('username', '').strip().lower()
        password = request.data.get('password', '').strip()

        if not username:
            return Response({'error': 'Username is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = UserProfile.objects.get(username__iexact=username)
        except UserProfile.DoesNotExist:
            return Response({'error': f"User '{username}' not found. Default usernames: venkatesh, alex, sarah, david"}, status=status.HTTP_404_NOT_FOUND)

        if user.password != password:
            return Response({'error': 'Invalid password. Default password for all users is 10'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = self.get_serializer(user)
        return Response({
            'message': f"Welcome back, {user.name}!",
            'user': serializer.data
        }, status=status.HTTP_200_OK)
