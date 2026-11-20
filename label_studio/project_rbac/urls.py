from django.urls import path
from organizations.views import simple_view

from . import accounts, api, workspaces

app_name = 'project_rbac'

urlpatterns = [
    # Page route of the single-page application: Organization > Accounts.
    path('organization/accounts', simple_view, name='organization-accounts'),
    path('api/projects/<int:pk>/roles/', api.ProjectRoleListAPI.as_view(), name='project-role-list'),
    path('api/projects/<int:pk>/roles/<int:user_pk>/', api.ProjectRoleDetailAPI.as_view(), name='project-role-detail'),
    path('api/rbac/me/', accounts.RbacMeAPI.as_view(), name='me'),
    path('api/rbac/accounts/', accounts.AccountListAPI.as_view(), name='account-list'),
    path('api/rbac/accounts/<int:pk>/', accounts.AccountDetailAPI.as_view(), name='account-detail'),
    path(
        'api/rbac/accounts/<int:pk>/reset-password/',
        accounts.AccountResetPasswordAPI.as_view(),
        name='account-reset-password',
    ),
    path('api/workspaces/', workspaces.WorkspaceListAPI.as_view(), name='workspace-list'),
    path('api/workspaces/<int:pk>/', workspaces.WorkspaceDetailAPI.as_view(), name='workspace-detail'),
    path('api/workspaces/<int:pk>/roles/', workspaces.WorkspaceRoleListAPI.as_view(), name='workspace-role-list'),
    path(
        'api/workspaces/<int:pk>/roles/<int:user_pk>/',
        workspaces.WorkspaceRoleDetailAPI.as_view(),
        name='workspace-role-detail',
    ),
    path('api/projects/<int:pk>/workspace/', workspaces.ProjectWorkspaceAPI.as_view(), name='project-workspace'),
]
