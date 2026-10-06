from organizations.models import OrganizationMember
from rest_framework import serializers

from .models import ProjectRole, Role


class ProjectRoleSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.ChoiceField(choices=Role.choices)

    class Meta:
        model = ProjectRole
        fields = ['user', 'email', 'role', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_user(self, user):
        project = self.context['project']
        is_member = OrganizationMember.objects.filter(
            user=user, organization_id=project.organization_id, deleted_at__isnull=True
        ).exists()
        if not is_member:
            raise serializers.ValidationError('User is not a member of the project organization.')
        return user
