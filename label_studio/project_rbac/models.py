"""Per-project role assignments."""

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
