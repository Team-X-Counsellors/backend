from rest_framework.permissions import BasePermission, IsAuthenticated


class IsStudent(BasePermission):
    message = 'Access restricted to students.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'student'


class IsCounselor(BasePermission):
    message = 'Access restricted to counselors.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'counselor'


class IsAdmin(BasePermission):
    message = 'Access restricted to administrators.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('admin', 'superadmin')


class IsSuperAdmin(BasePermission):
    message = 'Access restricted to super administrators.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'superadmin'


class IsCounselorOrAdmin(BasePermission):
    message = 'Access restricted to counselors and administrators.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in ('counselor', 'admin', 'superadmin')
        )


class IsAdminOrAuthor(BasePermission):
    """For forum content: admin can act on anything, author can act on own content."""

    def has_object_permission(self, request, view, obj):
        if request.user.role in ('admin', 'superadmin'):
            return True
        return hasattr(obj, 'author') and obj.author == request.user


class IsAnonymousSessionOwner(BasePermission):
    """
    Validates X-Shadow-Token header against the session's stored token_hash.
    Used for shadow chat endpoints that require no JWT.
    """
    message = 'Invalid or expired anonymous session token.'

    def has_object_permission(self, request, view, obj):
        from apps.shadow_chat.models import hash_token
        import secrets
        raw_token = request.headers.get('X-Shadow-Token', '')
        if not raw_token:
            return False
        return secrets.compare_digest(obj.token_hash, hash_token(raw_token))


class RolePermissionMixin:
    """
    ViewSet mixin for declaring per-action role permissions.

    Usage:
        role_permissions = {
            'create': [IsStudent],
            'destroy': [IsAdmin],
        }
    """
    role_permissions = {}

    def get_permissions(self):
        if self.action in self.role_permissions:
            return [perm() for perm in self.role_permissions[self.action]]
        return super().get_permissions()
