from rest_framework.permissions import BasePermission


class IsAdminForWrite(BasePermission):
    """Only admins may create/update/delete user accounts.

    Managers and employees can still be granted read access at the view
    level (e.g. a manager listing their own team).
    """

    def has_permission(self, request, view):
        user = request.user
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return bool(user and user.is_authenticated)
        return bool(user and user.is_authenticated and (user.is_superuser or user.role == 'ADMIN'))
