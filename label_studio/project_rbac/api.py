"""Role assignment API: ``/api/projects/<pk>/roles/``.

Access is decided by ``ProjectRolePermission``: the route names the project and
``ROLES_MANAGE`` is held by managers and organization admins only.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from projects.models import Project
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProjectRole
from .roles import ROLES_MANAGE
from .serializers import ProjectRoleSerializer


class ProjectRoleBaseAPI(APIView):
    permission_required = ROLES_MANAGE
    serializer_class = ProjectRoleSerializer

    def get_project(self):
        return get_object_or_404(Project.objects.for_user(self.request.user), pk=self.kwargs['pk'])


class ProjectRoleListAPI(ProjectRoleBaseAPI):
    @extend_schema(tags=['Project roles'], summary='List project roles', responses=ProjectRoleSerializer(many=True))
    def get(self, request, pk):
        project = self.get_project()
        roles = ProjectRole.objects.filter(project=project).select_related('user')
        return Response(ProjectRoleSerializer(roles, many=True, context={'project': project}).data)

    @extend_schema(
        tags=['Project roles'],
        summary='Assign a project role',
        request=ProjectRoleSerializer,
        responses=ProjectRoleSerializer,
    )
    def post(self, request, pk):
        """Assign a role, replacing the user's previous role on the project if any."""
        project = self.get_project()
        serializer = ProjectRoleSerializer(data=request.data, context={'project': project})
        serializer.is_valid(raise_exception=True)
        project_role, created = ProjectRole.objects.update_or_create(
            project=project,
            user=serializer.validated_data['user'],
            defaults={'role': serializer.validated_data['role']},
        )
        project.add_collaborator(project_role.user)
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(ProjectRoleSerializer(project_role, context={'project': project}).data, status=response_status)


class ProjectRoleDetailAPI(ProjectRoleBaseAPI):
    @extend_schema(tags=['Project roles'], summary='Revoke a project role', responses={204: None})
    def delete(self, request, pk, user_pk):
        project = self.get_project()
        get_object_or_404(ProjectRole, project=project, user_id=user_pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
