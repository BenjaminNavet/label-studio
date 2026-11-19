from django.apps import AppConfig


class ProjectRbacConfig(AppConfig):
    name = 'project_rbac'
    verbose_name = 'Project roles'

    def ready(self):
        from . import signals  # noqa: F401
