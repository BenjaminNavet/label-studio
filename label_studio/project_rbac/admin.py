from django.contrib import admin

from .models import ProjectRole, Workspace, WorkspaceProject, WorkspaceRole


@admin.register(ProjectRole)
class ProjectRoleAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'role', 'updated_at')
    list_filter = ('role',)
    search_fields = ('user__email', 'project__title')
    raw_id_fields = ('project', 'user')


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'created_by', 'updated_at')
    search_fields = ('title',)
    raw_id_fields = ('organization', 'created_by')


@admin.register(WorkspaceProject)
class WorkspaceProjectAdmin(admin.ModelAdmin):
    list_display = ('workspace', 'project', 'created_at')
    raw_id_fields = ('workspace', 'project')


@admin.register(WorkspaceRole)
class WorkspaceRoleAdmin(admin.ModelAdmin):
    list_display = ('workspace', 'user', 'role', 'updated_at')
    list_filter = ('role',)
    search_fields = ('user__email', 'workspace__title')
    raw_id_fields = ('workspace', 'user')
