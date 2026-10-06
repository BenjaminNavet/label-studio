from django.urls import path

from . import api

app_name = 'project_rbac'

urlpatterns = [
    path('api/projects/<int:pk>/roles/', api.ProjectRoleListAPI.as_view(), name='project-role-list'),
    path('api/projects/<int:pk>/roles/<int:user_pk>/', api.ProjectRoleDetailAPI.as_view(), name='project-role-detail'),
]
