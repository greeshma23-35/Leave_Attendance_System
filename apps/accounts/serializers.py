from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Full read/write representation of a user, used by admins."""

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            'id', 'employee_id', 'email', 'first_name', 'last_name', 'full_name',
            'phone_number', 'role', 'department', 'designation', 'manager',
            'manager_name', 'date_of_joining', 'profile_picture', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserCreateSerializer(serializers.ModelSerializer):
    """Used by admins to onboard a new employee/manager/admin account."""

    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = [
            'id', 'employee_id', 'email', 'password', 'first_name', 'last_name',
            'phone_number', 'role', 'department', 'designation', 'manager',
            'date_of_joining',
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class MyProfileSerializer(serializers.ModelSerializer):
    """A restricted serializer: employees can edit their own contact info,
    but not their role, manager, or employee_id (privilege escalation guard).
    """

    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'employee_id', 'email', 'first_name', 'last_name', 'full_name',
            'phone_number', 'role', 'department', 'designation', 'manager',
            'date_of_joining', 'profile_picture',
        ]
        read_only_fields = ['id', 'employee_id', 'email', 'role', 'manager', 'date_of_joining']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds useful, non-sensitive user claims to the JWT payload."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        token['full_name'] = user.get_full_name()
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
