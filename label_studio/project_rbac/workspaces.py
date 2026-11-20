"""Workspace API: ``/api/workspaces/`` and ``/api/projects/<pk>/workspace/`` (ADR 0004).

These views declare no ``permission_required``: a workspace is not a project, so the role matrix does
not apply. Each one calls a named rule of ``access.py`` instead.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class WorkspaceListAPI(APIView):
    def get(self, request):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def post(self, request):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class WorkspaceDetailAPI(APIView):
    def get(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def patch(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def delete(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class WorkspaceRoleListAPI(APIView):
    def get(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def post(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class WorkspaceRoleDetailAPI(APIView):
    def delete(self, request, pk, user_pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class ProjectWorkspaceAPI(APIView):
    def get(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def put(self, request, pk):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)
