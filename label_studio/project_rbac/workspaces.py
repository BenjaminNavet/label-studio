"""Workspace API: ``/api/workspaces/`` and ``/api/projects/<pk>/workspace/`` (ADR 0004).

These views declare no ``permission_required``: a workspace is not a project, so the role matrix does
not apply. Each one calls a named rule of ``access.py`` instead. A workspace the user cannot see answers
404, an action they may not take answers 403.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from projects.models import Project
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import (
    can_attach_project,
    can_delete_workspace,
    can_detach_project,
    can_manage_workspace,
    is_org_admin,
    is_owner,
    visible_workspaces,
)
from .models import Workspace, WorkspaceProject, WorkspaceRole
from .serializers import WorkspaceRoleSerializer, WorkspaceSerializer


class WorkspaceBaseAPI(APIView):
    serializer_class = WorkspaceSerializer

    def get_workspaces(self):
        return visible_workspaces(Workspace.objects.select_related('organization'), self.request.user)

    def get_workspace(self):
        return get_object_or_404(self.get_workspaces(), pk=self.kwargs['pk'])

    def get_managed_workspace(self):
        workspace = self.get_workspace()
        if not can_manage_workspace(self.request.user, workspace):
            raise PermissionDenied('Only a manager of this workspace can do this.')
        return workspace

    def serialize(self, workspaces, many=False):
        return WorkspaceSerializer(workspaces, many=many, context={'request': self.request}).data


class WorkspaceListAPI(WorkspaceBaseAPI):
    @extend_schema(tags=['Workspaces'], summary='List your workspaces', responses=WorkspaceSerializer(many=True))
    def get(self, request):
        return Response(self.serialize(self.get_workspaces(), many=True))

    @extend_schema(
        tags=['Workspaces'], summary='Create a workspace', request=WorkspaceSerializer, responses=WorkspaceSerializer
    )
    def post(self, request):
        """Any member creates a workspace and owns it; the manager role comes from a ``post_save`` signal."""
        serializer = WorkspaceSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save(organization=request.user.active_organization, created_by=request.user)
        return Response(self.serialize(workspace), status=status.HTTP_201_CREATED)


class WorkspaceDetailAPI(WorkspaceBaseAPI):
    @extend_schema(tags=['Workspaces'], summary='Get a workspace', responses=WorkspaceSerializer)
    def get(self, request, pk):
        return Response(self.serialize(self.get_workspace()))

    @extend_schema(
        tags=['Workspaces'], summary='Update a workspace', request=WorkspaceSerializer, responses=WorkspaceSerializer
    )
    def patch(self, request, pk):
        workspace = self.get_managed_workspace()
        serializer = WorkspaceSerializer(workspace, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(self.serialize(serializer.save()))

    @extend_schema(tags=['Workspaces'], summary='Delete a workspace', responses={204: None})
    def delete(self, request, pk):
        """Delete the workspace; its projects are detached, not deleted."""
        workspace = self.get_workspace()
        if not can_delete_workspace(request.user, workspace):
            raise PermissionDenied('Only the owner of this workspace can delete it.')
        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceRoleListAPI(WorkspaceBaseAPI):
    serializer_class = WorkspaceRoleSerializer

    @extend_schema(tags=['Workspaces'], summary='List workspace members', responses=WorkspaceRoleSerializer(many=True))
    def get(self, request, pk):
        workspace = self.get_managed_workspace()
        roles = WorkspaceRole.objects.filter(workspace=workspace).select_related('user', 'workspace')
        return Response(WorkspaceRoleSerializer(roles, many=True, context={'workspace': workspace}).data)

    @extend_schema(
        tags=['Workspaces'],
        summary='Assign a workspace role',
        request=WorkspaceRoleSerializer,
        responses=WorkspaceRoleSerializer,
    )
    def post(self, request, pk):
        """Give an existing account a role in the workspace, replacing a previous one."""
        workspace = self.get_managed_workspace()
        serializer = WorkspaceRoleSerializer(data=request.data, context={'workspace': workspace})
        serializer.is_valid(raise_exception=True)
        workspace_role, created = workspace.grant(serializer.validated_data['user'], serializer.validated_data['role'])
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        data = WorkspaceRoleSerializer(workspace_role, context={'workspace': workspace}).data
        return Response(data, status=response_status)


class WorkspaceRoleDetailAPI(WorkspaceBaseAPI):
    serializer_class = WorkspaceRoleSerializer

    @extend_schema(tags=['Workspaces'], summary='Revoke a workspace role', responses={204: None})
    def delete(self, request, pk, user_pk):
        workspace = self.get_managed_workspace()
        workspace_role = get_object_or_404(
            WorkspaceRole.objects.select_related('user'), workspace=workspace, user_id=user_pk
        )
        if is_owner(workspace_role.user, workspace):
            raise ValidationError({'user': 'The workspace owner cannot be removed from the workspace.'})
        workspace_role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectWorkspaceAPI(WorkspaceBaseAPI):
    """Which workspace a project is in, and moving it."""

    def get_project(self):
        return get_object_or_404(
            Project.objects.for_user(self.request.user).select_related('organization'), pk=self.kwargs['pk']
        )

    @staticmethod
    def current_workspace(project):
        link = WorkspaceProject.objects.filter(project=project).select_related('workspace__organization').first()
        return link.workspace if link else None

    def describe(self, project):
        user = self.request.user
        workspace = self.current_workspace(project)
        can_change = (
            is_org_admin(user, project.organization)
            or is_owner(user, project)
            or (workspace is not None and can_manage_workspace(user, workspace))
        )
        summary = {'id': workspace.id, 'title': workspace.title, 'color': workspace.color} if workspace else None
        return {'workspace': summary, 'can_change': can_change}

    @extend_schema(tags=['Workspaces'], summary='Get the workspace of a project')
    def get(self, request, pk):
        return Response(self.describe(self.get_project()))

    @extend_schema(tags=['Workspaces'], summary='Move a project into a workspace, or out of any')
    def put(self, request, pk):
        """Body ``{"workspace": <id>}`` places the project, ``{"workspace": null}`` takes it out."""
        project = self.get_project()
        if 'workspace' not in request.data:
            raise ValidationError({'workspace': 'Give a workspace id, or null for no workspace.'})
        target_id = request.data['workspace']
        current = self.current_workspace(project)

        if target_id is None:
            if current is not None:
                if not can_detach_project(request.user, project, current):
                    raise PermissionDenied('Only the project owner or a workspace manager can take it out.')
                WorkspaceProject.objects.filter(project=project).delete()
            return Response(self.describe(project))

        # A JSON boolean is an int in Python: only a real id names a workspace.
        is_id = isinstance(target_id, int) and not isinstance(target_id, bool)
        target = self.get_workspaces().filter(pk=target_id).first() if is_id else None
        if target is None:
            raise ValidationError({'workspace': 'No such workspace.'})
        if current is None or current.pk != target.pk:
            if not can_attach_project(request.user, project, target):
                raise PermissionDenied('Only the project owner, as a manager of the workspace, can place it there.')
            target.attach(project)
        return Response(self.describe(project))
