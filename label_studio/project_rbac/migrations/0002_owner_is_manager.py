from django.db import migrations


def grant_manager_role_to_owners(apps, schema_editor):
    """Projects created before ADR 0002: their creator becomes their manager."""
    Project = apps.get_model('projects', 'Project')
    ProjectRole = apps.get_model('project_rbac', 'ProjectRole')
    owners = Project.objects.filter(created_by__isnull=False).values_list('id', 'created_by_id')
    for project_id, owner_id in owners.iterator():
        ProjectRole.objects.update_or_create(project_id=project_id, user_id=owner_id, defaults={'role': 'manager'})


class Migration(migrations.Migration):
    dependencies = [
        ('project_rbac', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(grant_manager_role_to_owners, migrations.RunPython.noop),
    ]
