from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """Allows access only to users with the ADMIN role (or superusers)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.role == 'ADMIN'))


class IsManager(BasePermission):
    """Allows access only to users with the MANAGER role."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == 'MANAGER')


class IsManagerOrAdmin(BasePermission):
    """Allows access to managers and admins (used for approval-type actions)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and (user.is_superuser or user.role in ('MANAGER', 'ADMIN'))
        )


class IsSelfOrManagerOrAdmin(BasePermission):
    """Object-level permission: owner, their manager, or an admin can access."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        owner = getattr(obj, 'user', obj)  # obj itself may be the User

        if user.is_superuser or user.role == 'ADMIN':
            return True
        if owner == user:
            return True
        if user.role == 'MANAGER' and getattr(owner, 'manager_id', None) == user.id:
            return True
        return False


class ReadOnlyOrAdmin(BasePermission):
    """Anyone authenticated can read; only admins can write."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(user.is_superuser or user.role == 'ADMIN')
