"""Role assignments, per project and per workspace (ADR 0001, ADR 0004)."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    MANAGER = 'manager', _('Manager')
    REVIEWER = 'reviewer', _('Reviewer')
    ANNOTATOR = 'annotator', _('Annotator')


class ProjectRole(models.Model):
    """Grants one user one role on one project."""

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='rbac_roles')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_roles')
    role = models.CharField(max_length=16, choices=Role.choices)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'user'], name='project_rbac_unique_project_user')]
        ordering = ['project_id', 'user_id']

    def __str__(self):
        return f'{self.user} is {self.role} on project {self.project_id}'


class Workspace(models.Model):
    """A folder of projects whose members hold a role on every project it contains (ADR 0004)."""

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='rbac_workspaces'
    )
    title = models.CharField(_('title'), max_length=100)
    color = models.CharField(_('color'), max_length=16, default='#FDFDFC')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_workspaces'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        ordering = ['title', 'id']

    def __str__(self):
        return self.title

    def grant(self, user, role):
        """Give ``user`` a role in this workspace, replacing a previous one. Returns ``(workspace_role, created)``."""
        workspace_role, created = WorkspaceRole.objects.update_or_create(
            workspace=self, user=user, defaults={'role': role}
        )
        # Upstream user listings of the Data Manager read ProjectMember rows.
        for link in self.project_links.select_related('project'):
            link.project.add_collaborator(user)
        return workspace_role, created

    def attach(self, project):
        """Move ``project`` into this workspace: every member gains their workspace role on it."""
        WorkspaceProject.objects.update_or_create(project=project, defaults={'workspace': self})
        for workspace_role in self.roles.select_related('user'):
            project.add_collaborator(workspace_role.user)


class WorkspaceProject(models.Model):
    """Places one project in one workspace; a project belongs to one workspace at most."""

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='project_links')
    project = models.OneToOneField('projects.Project', on_delete=models.CASCADE, related_name='rbac_workspace')
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        ordering = ['workspace_id', 'project_id']

    def __str__(self):
        return f'project {self.project_id} in workspace {self.workspace_id}'


class WorkspaceRole(models.Model):
    """Grants one user one role on every project of one workspace."""

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='roles')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workspace_roles')
    role = models.CharField(max_length=16, choices=Role.choices)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['workspace', 'user'], name='project_rbac_unique_workspace_user')
        ]
        ordering = ['workspace_id', 'user_id']

    def __str__(self):
        return f'{self.user} is {self.role} in workspace {self.workspace_id}'
