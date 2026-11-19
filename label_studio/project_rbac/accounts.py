"""Account administration API, reserved to organization administrators (ADR 0003).

``/api/rbac/me/`` tells the interface whether the current user is an administrator.
``/api/rbac/accounts/`` lists, creates, updates and deactivates accounts and resets passwords.
"""

from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import is_org_admin


class IsOrgAdmin(BasePermission):
    """Grants access to organization administrators only."""

    message = 'Only an administrator can manage accounts.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and is_org_admin(user, user.active_organization))


class RbacMeAPI(APIView):
    """What the current user may do outside projects."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'is_admin': is_org_admin(request.user, request.user.active_organization)})


class AccountListAPI(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def get(self, request):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def post(self, request):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class AccountDetailAPI(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def patch(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class AccountResetPasswordAPI(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)
