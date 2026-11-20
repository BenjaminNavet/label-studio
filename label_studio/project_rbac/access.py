"""Access decisions: who is an organization admin, who sees which project or workspace, who may do what."""

from collections.abc import Mapping

from django.apps import apps
from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS

from .models import ProjectRole, Role, WorkspaceProject, WorkspaceRole
from .roles import (
    MANAGERS,
    MEMBER_ORGANIZATION_PERMISSIONS,
    OWN_OBJECT_PERMISSIONS,
    OWNER_ONLY,
    READ_ONLY_ORGANIZATION_PERMISSION,
    roles_allowed,
)

# Roles from the least to the most powerful: the effective role is the highest one held (ADR 0004).
ROLE_ORDER = (Role.ANNOTATOR, Role.REVIEWER, Role.MANAGER)
# Placeholder id for a referenced project or object that does not exist.
MISSING = -1
# Route prefixes whose ``pk`` is a project id.
PROJECT_PK_ROUTES = ('api/projects/<int:pk>', 'api/dm/projects/<int:pk>')
# Route prefixes whose ``pk`` is the id of a project-scoped object.
OBJECT_PK_ROUTES = {
    'api/tasks/<int:pk>': 'tasks.Task',
    'api/annotations/<int:pk>': 'tasks.Annotation',
    'api/drafts/<int:pk>': 'tasks.AnnotationDraft',
    'api/ml/<int:pk>': 'ml.MLBackend',
}
# FSM routes name their target as ``<entity_name>/<entity_id>``.
FSM_ENTITY_MODELS = {'project': 'projects.Project', 'task': 'tasks.Task', 'annotation': 'tasks.Annotation'}


def is_org_admin(user, organization):
    """Organization owners and superusers administer every project of the organization."""
    if user.is_superuser:
        return True
    return organization is not None and organization.created_by_id == user.id


def is_owner(user, owned):
    """The owner of a project or of a workspace is the user who created it (ADR 0002, ADR 0004)."""
    return owned.created_by_id is not None and owned.created_by_id == user.id


def highest_role(*roles):
    """Return the most powerful of ``roles``, ignoring None; None when none is held."""
    held = [role for role in roles if role is not None]
    return max(held, key=ROLE_ORDER.index) if held else None


def get_direct_role(user, project):
    """Return the role ``user`` was given on ``project`` itself, or None."""
    return ProjectRole.objects.filter(project=project, user=user).values_list('role', flat=True).first()


def get_workspace_role(user, workspace):
    """Return the user's role in ``workspace``, or None."""
    return WorkspaceRole.objects.filter(workspace=workspace, user=user).values_list('role', flat=True).first()


def get_inherited_role(user, project):
    """Return the role ``user`` holds in the workspace containing ``project``, or None."""
    return (
        WorkspaceRole.objects.filter(workspace__project_links__project=project, user=user)
        .values_list('role', flat=True)
        .first()
    )


def get_role(user, project):
    """Return the user's effective role on ``project``: the highest of the direct and the inherited one."""
    return highest_role(get_direct_role(user, project), get_inherited_role(user, project))


def _role_project_ids(user, roles=None):
    """Return two subqueries: the ids of the projects where ``user`` holds a direct role, and an inherited one.

    With ``roles``, only those roles count. Role sets are upward-closed (ADR 0004), so the effective role
    belongs to ``roles`` exactly when the direct role or the inherited role does: no need to compare them.
    """
    direct_roles = ProjectRole.objects.filter(user=user)
    workspace_roles = WorkspaceRole.objects.filter(user=user)
    if roles is not None:
        direct_roles = direct_roles.filter(role__in=roles)
        workspace_roles = workspace_roles.filter(role__in=roles)
    inherited = WorkspaceProject.objects.filter(workspace_id__in=workspace_roles.values('workspace_id'))
    return direct_roles.values('project_id'), inherited.values('project_id')


def in_user_projects(user, field='pk', roles=None):
    """Build the filter keeping rows whose ``field`` is a project where ``user`` holds a role (among ``roles``)."""
    direct, inherited = _role_project_ids(user, roles)
    return Q(**{f'{field}__in': direct}) | Q(**{f'{field}__in': inherited})


def holds_role_somewhere(user, roles):
    """Tell whether ``user`` holds one of ``roles`` on at least one project."""
    direct, inherited = _role_project_ids(user, roles)
    return direct.exists() or inherited.exists()


def visible_projects(queryset, user):
    """Restrict a project queryset to the projects ``user`` may see."""
    if is_org_admin(user, user.active_organization):
        return queryset
    return queryset.filter(in_user_projects(user))


def can_see_project(user, project):
    return is_org_admin(user, project.organization) or get_role(user, project) is not None


def role_allows(user, project, permission, obj=None):
    """Decide whether ``user`` may exercise ``permission`` on ``project`` (and on ``obj`` when given)."""
    if is_org_admin(user, project.organization):
        return True
    if permission in OWNER_ONLY:
        return is_owner(user, project)

    role = get_role(user, project)
    if role is None or role not in roles_allowed(permission):
        return False
    if role == Role.ANNOTATOR and permission in OWN_OBJECT_PERMISSIONS and obj is not None:
        return author_id(obj) == user.id
    return True


def organization_permission_allows(user, permission, method):
    """Decide an organization-level permission (accounts, invitations, organization settings; ADR 0003)."""
    if is_org_admin(user, user.active_organization):
        return True
    if permission in MEMBER_ORGANIZATION_PERMISSIONS:
        return True
    return permission == READ_ONLY_ORGANIZATION_PERMISSION and method in SAFE_METHODS


def _teammates(user, field):
    """Build the filter keeping rows whose ``field`` is a teammate of ``user``.

    Teammates hold a role, direct or inherited, on a project where ``user`` holds one, or belong to one
    of the user's workspaces.
    """
    shared_projects = in_user_projects(user, 'project_id')
    direct_teammates = ProjectRole.objects.filter(shared_projects).values('user_id')
    own_workspaces = WorkspaceRole.objects.filter(user=user).values('workspace_id')
    workspaces_of_shared_projects = WorkspaceProject.objects.filter(shared_projects).values('workspace_id')
    workspace_teammates = WorkspaceRole.objects.filter(
        Q(workspace_id__in=own_workspaces) | Q(workspace_id__in=workspaces_of_shared_projects)
    ).values('user_id')
    return Q(**{f'{field}__in': direct_teammates}) | Q(**{f'{field}__in': workspace_teammates})


def visible_users(queryset, user):
    """Restrict a user queryset to ``user`` and the people sharing at least one project with them."""
    if is_org_admin(user, user.active_organization):
        return queryset
    return queryset.filter(Q(pk=user.pk) | _teammates(user, 'pk'))


def visible_members(queryset, user):
    """Same restriction as ``visible_users``, for a queryset of organization members."""
    if is_org_admin(user, user.active_organization):
        return queryset
    return queryset.filter(Q(user=user) | _teammates(user, 'user'))


def author_id(obj):
    """Return the id of the user who authored an annotation or draft, else None."""
    if hasattr(obj, 'completed_by_id'):
        return obj.completed_by_id
    return getattr(obj, 'user_id', None)


def project_of(obj):
    """Return the project an object belongs to, or None when it is not project-scoped."""
    Project = apps.get_model('projects', 'Project')
    if isinstance(obj, Project):
        return obj
    project = getattr(obj, 'project', None)
    if isinstance(project, Project):
        return project
    task = getattr(obj, 'task', None)
    return getattr(task, 'project', None)


def _project_id_for_object(model, pk):
    field_names = {field.name for field in model._meta.get_fields()}
    if 'project' in field_names:
        return model.objects.filter(pk=pk).values_list('project_id', flat=True).first()
    if 'task' in field_names:
        return model.objects.filter(pk=pk).values_list('task__project_id', flat=True).first()
    return None


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_project_ids(request, view):
    """Collect every project a request may target, from its route, query string and body.

    A view may read its project from any of these places, so all of them are checked: a request naming
    project A in the query string and project B in the body is judged on both. ``MISSING`` stands for a
    referenced object or project that does not exist.
    """
    project_ids = set()
    kwargs = getattr(view, 'kwargs', {}) or {}
    # Apps are included under re_path(r'^', ...), so routes start with a regex anchor.
    route = (getattr(request.resolver_match, 'route', '') or '').lstrip('^')
    pk = _as_int(kwargs.get('pk'))

    if pk is not None:
        if route.startswith(PROJECT_PK_ROUTES):
            project_ids.add(pk)
        else:
            model = next(
                (apps.get_model(label) for prefix, label in OBJECT_PK_ROUTES.items() if route.startswith(prefix)),
                getattr(getattr(view, 'queryset', None), 'model', None),
            )
            if model is not None:
                project_ids.add(_project_id_for_object(model, pk))

    entity_name, entity_id = kwargs.get('entity_name'), _as_int(kwargs.get('entity_id'))
    if entity_name is not None and entity_id is not None:
        model_label = FSM_ENTITY_MODELS.get(entity_name)
        if model_label is None:
            project_ids.add(MISSING)
        elif model_label == 'projects.Project':
            project_ids.add(entity_id)
        else:
            project_ids.add(_project_id_for_object(apps.get_model(model_label), entity_id) or MISSING)

    if 'project' in request.query_params:
        project_ids.add(_as_int(request.query_params.get('project')) or MISSING)
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and isinstance(request.data, Mapping):
        # An explicit null detaches the object from its project (an organization-wide webhook, for instance).
        if 'project' in request.data:
            project_ids.add(_as_int(request.data.get('project')) or MISSING)
        if request.data.get('task') is not None:
            task_model = apps.get_model('tasks', 'Task')
            project_ids.add(_project_id_for_object(task_model, _as_int(request.data.get('task'))) or MISSING)

    project_ids.discard(None)
    return project_ids


def managed_by(queryset, user, project_field='project'):
    """Restrict a queryset of project-scoped objects to the projects ``user`` manages.

    Organization admins keep everything, including objects attached to no project.
    """
    if is_org_admin(user, user.active_organization):
        return queryset
    return queryset.filter(in_user_projects(user, project_field, roles=MANAGERS))


def visible_workspaces(queryset, user):
    """Restrict a workspace queryset to those ``user`` may see: their own, or all of them for an administrator."""
    queryset = queryset.filter(organization=user.active_organization)
    if is_org_admin(user, user.active_organization):
        return queryset
    return queryset.filter(pk__in=WorkspaceRole.objects.filter(user=user).values('workspace_id'))


def can_manage_workspace(user, workspace):
    """Renaming a workspace and managing its members belong to its managers."""
    return is_org_admin(user, workspace.organization) or get_workspace_role(user, workspace) == Role.MANAGER


def can_delete_workspace(user, workspace):
    """Deleting a workspace belongs to its owner, as deleting a project does (ADR 0002)."""
    return is_org_admin(user, workspace.organization) or is_owner(user, workspace)


def can_attach_project(user, project, workspace):
    """Placing a project in a workspace opens it to every member: only its owner may, into a workspace they manage."""
    if is_org_admin(user, project.organization):
        return True
    return is_owner(user, project) and get_workspace_role(user, workspace) == Role.MANAGER


def can_detach_project(user, project, workspace):
    """Taking a project out of its workspace belongs to the project owner and to the workspace managers."""
    if is_org_admin(user, project.organization) or is_owner(user, project):
        return True
    return get_workspace_role(user, workspace) == Role.MANAGER
