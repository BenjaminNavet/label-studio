from django.contrib.auth import get_user_model
from organizations.models import OrganizationMember
from rest_framework import serializers

from .access import is_owner
from .models import ProjectRole, Role

User = get_user_model()


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
        email = attrs.pop('email', None)
        user = attrs.get('user')
        if user is None and email is None:
            raise serializers.ValidationError({'email': 'Give the email address of the person to invite.'})
        if user is None:
            user = User.objects.filter(email__iexact=email).first()

        is_member = (
            user is not None
            and OrganizationMember.objects.filter(
                user=user, organization_id=project.organization_id, deleted_at__isnull=True
            ).exists()
        )
        if not is_member:
            field = 'email' if email is not None else 'user'
            raise serializers.ValidationError(
                {field: 'No account matches. Ask an administrator to create the account first.'}
            )
        if not user.is_active:
            raise serializers.ValidationError({'email': 'This account is deactivated.'})
        if is_owner(user, project) and attrs['role'] != Role.MANAGER:
            raise serializers.ValidationError({'role': 'The project owner always is a manager.'})

        attrs['user'] = user
        return attrs

    def to_representation(self, instance):
        user = instance.user
        return {
            'user': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': instance.role,
            'is_owner': is_owner(user, instance.project),
            'created_at': serializers.DateTimeField().to_representation(instance.created_at),
            'updated_at': serializers.DateTimeField().to_representation(instance.updated_at),
        }


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
        return ProjectRole.objects.filter(user=user).count()

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
