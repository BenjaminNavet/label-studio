"""Role matrix: which project role may exercise which permission.

Permission names are the ones views declare in ``permission_required``
(see ``core.permissions.AllPermissions``). A permission missing from
``ROLE_MATRIX`` is reserved to managers: unknown means denied, not granted.
"""

from rest_framework.permissions import SAFE_METHODS

from .models import Role

ALL_ROLES = frozenset({Role.MANAGER, Role.REVIEWER, Role.ANNOTATOR})
MANAGERS = frozenset({Role.MANAGER})

# Pseudo-permission for read access to predictions, which upstream folds into ``predictions.any``.
PREDICTIONS_VIEW = 'predictions.view'
# Pseudo-permission guarding the role-assignment API of this app.
ROLES_MANAGE = 'project_rbac.manage'

ROLE_MATRIX = {
    'projects.view': ALL_ROLES,
    'tasks.view': ALL_ROLES,
    'annotations.view': ALL_ROLES,
    'annotations.create': ALL_ROLES,
    # Annotators are further limited to their own annotations, see ``OWN_OBJECT_PERMISSIONS``.
    'annotations.change': ALL_ROLES,
    'annotations.delete': ALL_ROLES,
    'labels.view': ALL_ROLES,
    PREDICTIONS_VIEW: ALL_ROLES,
    # Data Manager tabs: the labeling UI creates a default tab on first visit.
    'views.view': ALL_ROLES,
    'views.create': ALL_ROLES,
    'views.change': ALL_ROLES,
    'views.delete': ALL_ROLES,
}

# Permissions only an organization administrator holds, whatever the project role.
ORG_ADMIN_ONLY = frozenset({'projects.create', 'projects.delete'})

# Organization-level permissions, outside the project role model: upstream behaviour is kept.
NON_PROJECT_PERMISSION_PREFIXES = ('organizations.', 'users.', 'avatar.')

# Permissions an annotator holds only on objects they authored.
OWN_OBJECT_PERMISSIONS = frozenset({'annotations.change', 'annotations.delete'})

# Upstream declares a permission that is too broad for some endpoints: (view class name, method) -> permission.
VIEW_PERMISSION_OVERRIDES = {
    # Data Manager actions include deleting tasks and annotations, yet upstream guards POST with projects.view.
    ('ProjectActionsAPI', 'POST'): 'actions.perform',
}


def roles_allowed(permission):
    """Return the roles that hold ``permission`` (managers only when unlisted)."""
    return ROLE_MATRIX.get(permission, MANAGERS)


def required_permission(view, method):
    """Return the permission ``view`` requires for HTTP ``method``, or None when it declares none."""
    method = 'GET' if method == 'HEAD' else method
    override = VIEW_PERMISSION_OVERRIDES.get((type(view).__name__, method))
    if override:
        return override

    declared = getattr(view, 'permission_required', None)
    if declared is None:
        return None
    permission = declared if isinstance(declared, str) else getattr(declared, method, None)
    if permission == 'predictions.any' and method in SAFE_METHODS:
        return PREDICTIONS_VIEW
    return permission
