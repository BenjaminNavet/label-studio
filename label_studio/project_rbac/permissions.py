"""DRF permission applying the role matrix to every view that declares ``permission_required``."""

from django.apps import apps
from rest_framework.permissions import BasePermission

# DRF imports DEFAULT_PERMISSION_CLASSES while settings load, before the app registry is ready:
# every import that touches models stays inside the methods.


class ProjectRolePermission(BasePermission):
    """Replaces ``core.api_permissions.HasObjectPermission`` in ``DEFAULT_PERMISSION_CLASSES``."""

    message = 'Your role on this project does not allow this action.'

    def has_permission(self, request, view):
        from .access import is_org_admin, resolve_project_id, role_allows
        from .roles import ORG_ADMIN_ONLY, required_permission

        user = request.user
        if not user or not user.is_authenticated:
            # Authentication is IsAuthenticated's job; let it produce the 401.
            return True
        permission = required_permission(view, request.method)
        if permission is None:
            return True

        project_id = resolve_project_id(request, view)
        if project_id is None:
            if permission in ORG_ADMIN_ONLY:
                return is_org_admin(user, user.active_organization)
            return True
        project = (
            apps.get_model('projects', 'Project').objects.filter(pk=project_id).select_related('organization').first()
        )
        if project is None:
            # Unknown project: let the view answer 404.
            return True
        return role_allows(user, project, permission)

    def has_object_permission(self, request, view, obj):
        from .access import project_of, role_allows
        from .roles import required_permission

        if not obj.has_permission(request.user):
            return False
        permission = required_permission(view, request.method)
        project = project_of(obj)
        if permission is None or project is None:
            return True
        return role_allows(request.user, project, permission, obj)
