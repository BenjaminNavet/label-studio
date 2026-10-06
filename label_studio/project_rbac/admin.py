from django.contrib import admin

from .models import ProjectRole


@admin.register(ProjectRole)
class ProjectRoleAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'role', 'updated_at')
    list_filter = ('role',)
    search_fields = ('user__email', 'project__title')
    raw_id_fields = ('project', 'user')
