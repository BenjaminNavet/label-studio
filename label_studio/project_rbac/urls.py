from django.urls import path
from organizations.views import simple_view

from . import accounts, api

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
]
