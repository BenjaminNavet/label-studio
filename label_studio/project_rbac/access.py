"""Access decisions: who is an organization admin, who sees which project, who may do what."""

from collections.abc import Mapping

from django.apps import apps

from .models import ProjectRole, Role
from .roles import ORG_ADMIN_ONLY, OWN_OBJECT_PERMISSIONS, roles_allowed

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


def is_org_admin(user, organization):
    """Organization owners and superusers administer every project of the organization."""
    if user.is_superuser:
        return True
    return organization is not None and organization.created_by_id == user.id


def get_role(user, project):
    """Return the user's role on ``project``, or None."""
    return ProjectRole.objects.filter(project=project, user=user).values_list('role', flat=True).first()


def visible_projects(queryset, user):
    """Restrict a project queryset to the projects ``user`` may see."""
    if is_org_admin(user, user.active_organization):
        return queryset
    return queryset.filter(rbac_roles__user=user)


def can_see_project(user, project):
    return is_org_admin(user, project.organization) or get_role(user, project) is not None


def role_allows(user, project, permission, obj=None):
    """Decide whether ``user`` may exercise ``permission`` on ``project`` (and on ``obj`` when given)."""
    if is_org_admin(user, project.organization):
        return True
    if permission in ORG_ADMIN_ONLY:
        return False

    role = get_role(user, project)
    if role is None or role not in roles_allowed(permission):
        return False
    if role == Role.ANNOTATOR and permission in OWN_OBJECT_PERMISSIONS and obj is not None:
        return author_id(obj) == user.id
    return True


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

    if 'project' in request.query_params:
        project_ids.add(_as_int(request.query_params.get('project')) or MISSING)
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and isinstance(request.data, Mapping):
        if request.data.get('project') is not None:
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
    managed_project_ids = ProjectRole.objects.filter(user=user, role=Role.MANAGER).values('project_id')
    return queryset.filter(**{f'{project_field}__in': managed_project_ids})
