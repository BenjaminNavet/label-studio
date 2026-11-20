"""Query-string filters that upstream list views borrow from this app."""


def filter_projects_by_workspace(queryset, name, value):
    """Keep the projects of one workspace (``?workspace=<id>``) or those outside any (``?workspace=none``).

    Applied on top of the visibility filter: naming a workspace reveals nothing the user could not see.
    """
    if value == 'none':
        return queryset.filter(rbac_workspace__isnull=True)
    try:
        workspace_id = int(value)
    except ValueError:
        return queryset.none()
    return queryset.filter(rbac_workspace__workspace_id=workspace_id)
