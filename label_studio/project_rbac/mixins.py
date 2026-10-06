"""Project mixin enforcing per-project visibility, loaded through the ``PROJECT_MIXIN`` setting."""

from projects.mixins import ProjectMixin

from .access import can_see_project


class RBACProjectMixin(ProjectMixin):
    def has_permission(self, user):
        # Tasks, annotations, predictions, storages, exports and ML backends all delegate here.
        return super().has_permission(user) and can_see_project(user, self)
