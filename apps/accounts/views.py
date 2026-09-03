from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .permissions import IsAdminForWrite
from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    MyProfileSerializer,
    UserCreateSerializer,
    UserSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """POST {email, password} -> {access, refresh, user}."""

    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    Admin: full CRUD over every employee/manager account.
    Manager: read-only access to themself + their direct reports.
    Employee: read-only access to their own record only.
    """

    permission_classes = [IsAuthenticated, IsAdminForWrite]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'department', 'is_active', 'manager']
    search_fields = ['first_name', 'last_name', 'email', 'employee_id']
    ordering_fields = ['first_name', 'date_of_joining', 'created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == User.Role.ADMIN:
            return User.objects.all()
        if user.role == User.Role.MANAGER:
            return User.objects.filter(Q(id=user.id) | Q(manager=user))
        return User.objects.filter(id=user.id)


class MyProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH the currently authenticated user's own profile."""

    serializer_class = MyProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """POST {old_password, new_password} to change your own password."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)
