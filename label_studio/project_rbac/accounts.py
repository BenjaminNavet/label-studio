"""Account administration API, reserved to organization administrators (ADR 0003).

``/api/rbac/me/`` tells the interface whether the current user is an administrator.
``/api/rbac/accounts/`` lists, creates, updates and deactivates accounts and resets passwords.
Passwords are generated here and returned once: nothing stores them in clear.
"""

import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import is_org_admin
from .serializers import AccountSerializer

User = get_user_model()

# 16 URL-safe characters, about 96 bits of entropy.
GENERATED_PASSWORD_BYTES = 12


def generate_password():
    return secrets.token_urlsafe(GENERATED_PASSWORD_BYTES)


class IsOrgAdmin(BasePermission):
    """Grants access to organization administrators only."""

    message = 'Only an administrator can manage accounts.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and is_org_admin(user, user.active_organization))


class RbacMeAPI(APIView):
    """What the current user may do outside projects."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Accounts'], summary='Rights of the current user outside projects')
    def get(self, request):
        return Response({'is_admin': is_org_admin(request.user, request.user.active_organization)})


class AccountBaseAPI(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    serializer_class = AccountSerializer

    def get_accounts(self):
        """Accounts of the administrator's organization, deactivated ones included."""
        return User.objects.filter(organizations=self.request.user.active_organization).order_by('email')

    def get_serializer_context(self):
        return {'request': self.request, 'organization': self.request.user.active_organization}

    def serialize(self, account):
        return AccountSerializer(account, context=self.get_serializer_context()).data


class AccountListAPI(AccountBaseAPI):
    @extend_schema(tags=['Accounts'], summary='List accounts', responses=AccountSerializer(many=True))
    def get(self, request):
        accounts = self.get_accounts()
        return Response(AccountSerializer(accounts, many=True, context=self.get_serializer_context()).data)

    @extend_schema(tags=['Accounts'], summary='Create an account', request=AccountSerializer)
    def post(self, request):
        """Create an account in the organization and return its generated password, once."""
        serializer = AccountSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        fields = serializer.validated_data

        password = generate_password()
        organization = request.user.active_organization
        with transaction.atomic():
            account = User.objects.create_user(
                email=fields['email'],
                password=password,
                username=fields['email'].split('@')[0],
                first_name=fields.get('first_name', ''),
                last_name=fields.get('last_name', ''),
                is_superuser=fields.get('is_superuser', False),
                is_active=fields.get('is_active', True),
            )
            organization.add_user(account)
            account.active_organization = organization
            account.save(update_fields=['active_organization'])
        return Response({**self.serialize(account), 'password': password}, status=status.HTTP_201_CREATED)


class AccountDetailAPI(AccountBaseAPI):
    @extend_schema(tags=['Accounts'], summary='Update an account', request=AccountSerializer)
    def patch(self, request, pk):
        """Change the name, the email, the active state or the administrator state of an account."""
        account = get_object_or_404(self.get_accounts(), pk=pk)
        serializer = AccountSerializer(account, data=request.data, partial=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self.serialize(account))


class AccountResetPasswordAPI(AccountBaseAPI):
    @extend_schema(tags=['Accounts'], summary='Reset the password of an account', request=None)
    def post(self, request, pk):
        """Replace the password with a generated one, returned once; open sessions of the account end."""
        account = get_object_or_404(self.get_accounts(), pk=pk)
        password = generate_password()
        account.set_password(password)
        account.save(update_fields=['password'])
        return Response({'password': password})
