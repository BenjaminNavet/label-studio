"""Keeps project roles in step with project creation (ADR 0002)."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ProjectRole, Role


@receiver(post_save, sender='projects.Project', dispatch_uid='project_rbac_owner_is_manager')
def grant_manager_role_to_owner(sender, instance, created, **kwargs):
    """The creator of a project owns it: every creation path (API, import, duplication) ends here."""
    if created and instance.created_by_id is not None:
        ProjectRole.objects.update_or_create(
            project=instance, user_id=instance.created_by_id, defaults={'role': Role.MANAGER}
        )
