import re

from django.apps import apps
from django.contrib.auth import get_user_model
from organizations.models import OrganizationMember
from rest_framework import serializers

from .access import (
    can_delete_workspace,
    can_manage_workspace,
    get_workspace_role,
    in_user_projects,
    is_owner,
)
from .models import ProjectRole, Role, Workspace, WorkspaceRole

User = get_user_model()

COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')


def resolve_member(attrs, organization_id):
    """Find the account a role assignment names, by ``user`` id or by ``email``.

    The account must exist, belong to the organization and be active: accounts are created by
    administrators (ADR 0003), an unknown address is refused.
    """
    email = attrs.pop('email', None)
    user = attrs.get('user')
    if user is None and email is None:
        raise serializers.ValidationError({'email': 'Give the email address of the person to invite.'})
    if user is None:
        user = User.objects.filter(email__iexact=email).first()

    is_member = (
        user is not None
        and OrganizationMember.objects.filter(
            user=user, organization_id=organization_id, deleted_at__isnull=True
        ).exists()
    )
    if not is_member:
        field = 'email' if email is not None else 'user'
        raise serializers.ValidationError(
            {field: 'No account matches. Ask an administrator to create the account first.'}
        )
    if not user.is_active:
        raise serializers.ValidationError({'email': 'This account is deactivated.'})
    return user


def member_row(user, role, owned, timestamps):
    """Describe one member of a project or of a workspace (``owned``) as the role APIs return it."""
    to_text = serializers.DateTimeField().to_representation
    return {
        'user': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': role,
        'is_owner': is_owner(user, owned),
        'created_at': to_text(timestamps.created_at),
        'updated_at': to_text(timestamps.updated_at),
    }


def inherited_roles_of(project):
    """Map user id to the workspace role each member of the project's workspace holds."""
    return {
        workspace_role.user_id: workspace_role
        for workspace_role in WorkspaceRole.objects.filter(workspace__project_links__project=project).select_related(
            'user'
        )
    }


def project_member_rows(project):
    """List everyone holding a role on ``project``, direct or inherited from its workspace (ADR 0004).

    ``role`` is the direct role, None for a member who only comes through the workspace;
    ``workspace_role`` is the inherited one, None outside the workspace.
    """
    direct_roles = {
        project_role.user_id: project_role
        for project_role in ProjectRole.objects.filter(project=project).select_related('user')
    }
    inherited_roles = inherited_roles_of(project)
    rows = []
    for user_id in sorted(direct_roles.keys() | inherited_roles.keys()):
        direct, inherited = direct_roles.get(user_id), inherited_roles.get(user_id)
        source = direct or inherited
        row = member_row(source.user, direct.role if direct else None, project, source)
        row['workspace_role'] = inherited.role if inherited else None
        rows.append(row)
    return rows


class ProjectRoleSerializer(serializers.ModelSerializer):
    """A project role; the member is named by ``user`` (id) or by ``email`` when assigning."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    email = serializers.EmailField(required=False, write_only=True)
    role = serializers.ChoiceField(choices=Role.choices)

    class Meta:
        model = ProjectRole
        fields = ['user', 'email', 'role', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        project = self.context['project']
        user = resolve_member(attrs, project.organization_id)
        if is_owner(user, project) and attrs['role'] != Role.MANAGER:
            raise serializers.ValidationError({'role': 'The project owner always is a manager.'})

        attrs['user'] = user
        return attrs

    def to_representation(self, instance):
        row = member_row(instance.user, instance.role, instance.project, instance)
        inherited = inherited_roles_of(instance.project).get(instance.user_id)
        row['workspace_role'] = inherited.role if inherited else None
        return row


class WorkspaceRoleSerializer(serializers.ModelSerializer):
    """A workspace role; the member is named by ``user`` (id) or by ``email`` when assigning."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    email = serializers.EmailField(required=False, write_only=True)
    role = serializers.ChoiceField(choices=Role.choices)

    class Meta:
        model = WorkspaceRole
        fields = ['user', 'email', 'role', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        workspace = self.context['workspace']
        user = resolve_member(attrs, workspace.organization_id)
        if is_owner(user, workspace) and attrs['role'] != Role.MANAGER:
            raise serializers.ValidationError({'role': 'The workspace owner always is a manager.'})

        attrs['user'] = user
        return attrs

    def to_representation(self, instance):
        return member_row(instance.user, instance.role, instance.workspace, instance)


class WorkspaceSerializer(serializers.ModelSerializer):
    """A workspace as the requesting user sees it: their role in it and what they may do with it."""

    is_owner = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    project_count = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            'id',
            'title',
            'color',
            'created_by',
            'is_owner',
            'role',
            'can_manage',
            'can_delete',
            'project_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate_title(self, title):
        title = title.strip()
        if not title:
            raise serializers.ValidationError('Give the workspace a name.')
        return title

    def validate_color(self, color):
        if not COLOR_PATTERN.match(color):
            raise serializers.ValidationError('Give the color as #RRGGBB.')
        return color

    def get_is_owner(self, workspace) -> bool:
        return is_owner(self.context['request'].user, workspace)

    def get_role(self, workspace) -> str | None:
        return get_workspace_role(self.context['request'].user, workspace)

    def get_can_manage(self, workspace) -> bool:
        return can_manage_workspace(self.context['request'].user, workspace)

    def get_can_delete(self, workspace) -> bool:
        return can_delete_workspace(self.context['request'].user, workspace)

    def get_project_count(self, workspace) -> int:
        return workspace.project_links.count()


class AccountSerializer(serializers.ModelSerializer):
    """An account as administrators see it; ``is_admin`` maps to ``is_superuser``."""

    email = serializers.EmailField()
    is_admin = serializers.BooleanField(source='is_superuser', required=False)
    is_owner = serializers.SerializerMethodField()
    project_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'is_admin',
            'is_owner',
            'last_activity',
            'date_joined',
            'project_count',
        ]
        read_only_fields = ['id', 'last_activity', 'date_joined']

    def get_is_owner(self, user) -> bool:
        return self.context['organization'].created_by_id == user.id

    def get_project_count(self, user) -> int:
        # Projects reached through a workspace count too (ADR 0004).
        return apps.get_model('projects', 'Project').objects.filter(in_user_projects(user)).count()

    def validate_email(self, email):
        email = email.strip().lower()
        duplicates = User.objects.filter(email__iexact=email)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return email

    def validate(self, attrs):
        account = self.instance
        if account is None:
            return attrs
        loses_access = attrs.get('is_active') is False and account.is_active
        loses_admin = attrs.get('is_superuser') is False and account.is_superuser
        if loses_access or loses_admin:
            if account.pk == self.context['request'].user.pk:
                raise serializers.ValidationError('You cannot deactivate or demote your own account.')
            if self.get_is_owner(account):
                raise serializers.ValidationError('The organization owner cannot be deactivated or demoted.')
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # The organization owner administers it whatever the superuser flag says.
        data['is_admin'] = instance.is_superuser or data['is_owner']
        return data
