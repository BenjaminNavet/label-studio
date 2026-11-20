"""Keeps roles in step with the creation of projects (ADR 0002) and workspaces (ADR 0004)."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ProjectRole, Role, Workspace, WorkspaceRole


@receiver(post_save, sender='projects.Project', dispatch_uid='project_rbac_owner_is_manager')
def grant_manager_role_to_owner(sender, instance, created, **kwargs):
    """The creator of a project owns it: every creation path (API, import, duplication) ends here."""
    if created and instance.created_by_id is not None:
        ProjectRole.objects.update_or_create(
            project=instance, user_id=instance.created_by_id, defaults={'role': Role.MANAGER}
        )


@receiver(post_save, sender=Workspace, dispatch_uid='project_rbac_workspace_owner_is_manager')
def grant_manager_role_to_workspace_owner(sender, instance, created, **kwargs):
    """The creator of a workspace owns it and manages it."""
    if created and instance.created_by_id is not None:
        WorkspaceRole.objects.update_or_create(
            workspace=instance, user_id=instance.created_by_id, defaults={'role': Role.MANAGER}
        )
