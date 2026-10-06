"""DRF permission applying the role matrix to every view that declares ``permission_required``."""

from django.apps import apps
from rest_framework.permissions import SAFE_METHODS, BasePermission

# DRF imports DEFAULT_PERMISSION_CLASSES while settings load, before the app registry is ready:
# every import that touches models stays inside the methods.


class ProjectRolePermission(BasePermission):
    """Replaces ``core.api_permissions.HasObjectPermission`` in ``DEFAULT_PERMISSION_CLASSES``."""

    message = 'Your role on this project does not allow this action.'

    def has_permission(self, request, view):
        from .access import MISSING, is_org_admin, resolve_project_ids, role_allows
        from .models import ProjectRole, Role
        from .roles import NON_PROJECT_PERMISSION_PREFIXES, ORG_ADMIN_ONLY, required_permission, roles_allowed

        user = request.user
        if not user or not user.is_authenticated:
            # Authentication is IsAuthenticated's job; let it produce the 401.
            return True
        permission = required_permission(view, request.method)
        if permission is None or permission.startswith(NON_PROJECT_PERMISSION_PREFIXES):
            return True
        if is_org_admin(user, user.active_organization):
            return True
        if permission in ORG_ADMIN_ONLY:
            return False

        project_ids = resolve_project_ids(request, view)
        if not project_ids and request.method not in SAFE_METHODS:
            # A write that names no project would create or change an organization-wide object.
            return False
        if not project_ids:
            # No project named: object-level checks and filtered querysets take over. A permission
            # limited to some roles still requires holding one of those roles somewhere.
            allowed_roles = roles_allowed(permission)
            if Role.ANNOTATOR in allowed_roles:
                # Every role holds it: listings are filtered by project visibility, not refused.
                return True
            return ProjectRole.objects.filter(user=user, role__in=allowed_roles).exists()
        if MISSING in project_ids:
            return False
        projects = list(
            apps.get_model('projects', 'Project').objects.filter(pk__in=project_ids).select_related('organization')
        )
        if len(projects) != len(project_ids):
            return False
        return all(role_allows(user, project, permission) for project in projects)

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
