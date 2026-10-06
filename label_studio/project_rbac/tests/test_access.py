"""Security tests: what each project role can see and do through the public API."""

import pytest
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from project_rbac.models import ProjectRole, Role
from projects.models import Project
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from tasks.tests.factories import AnnotationFactory, TaskFactory
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HIDDEN = (403, 404)
LABEL_CONFIG = (
    '<View><Text name="text" value="$text"/>'
    '<Choices name="label" toName="text"><Choice value="a"/><Choice value="b"/></Choices></View>'
)


@pytest.fixture
def world():
    """One organization, two projects; project A has a manager, a reviewer and an annotator."""
    organization = OrganizationFactory()
    admin = organization.created_by
    project_a = ProjectFactory(organization=organization, label_config=LABEL_CONFIG)
    project_b = ProjectFactory(organization=organization, label_config=LABEL_CONFIG)

    people = {'admin': admin}
    for name in ('manager', 'reviewer', 'annotator', 'outsider'):
        people[name] = UserFactory(active_organization=organization)
    for name, role in (('manager', Role.MANAGER), ('reviewer', Role.REVIEWER), ('annotator', Role.ANNOTATOR)):
        ProjectRole.objects.create(project=project_a, user=people[name], role=role)

    task_a = TaskFactory(project=project_a, data={'text': 'a'})
    task_b = TaskFactory(project=project_b, data={'text': 'b'})
    return {
        'organization': organization,
        'people': people,
        'project_a': project_a,
        'project_b': project_b,
        'task_a': task_a,
        'task_b': task_b,
        'annotation_by_annotator': AnnotationFactory(task=task_a, completed_by=people['annotator']),
        'annotation_by_reviewer': AnnotationFactory(task=task_a, completed_by=people['reviewer']),
    }


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def listed_project_ids(user):
    response = client_for(user).get('/api/projects/', {'page_size': 100})
    assert response.status_code == 200
    return {project['id'] for project in response.json()['results']}


class TestVisibility:
    def test_admin_lists_every_project(self, world):
        assert listed_project_ids(world['people']['admin']) == {world['project_a'].id, world['project_b'].id}

    def test_member_lists_only_assigned_projects(self, world):
        assert listed_project_ids(world['people']['annotator']) == {world['project_a'].id}

    def test_outsider_lists_nothing(self, world):
        assert listed_project_ids(world['people']['outsider']) == set()

    def test_counts_endpoint_is_filtered(self, world):
        response = client_for(world['people']['annotator']).get('/api/projects/counts/', {'page_size': 100})
        assert response.status_code == 200
        assert {project['id'] for project in response.json()['results']} == {world['project_a'].id}

    def test_project_detail_hidden_without_role(self, world):
        annotator = client_for(world['people']['annotator'])
        assert annotator.get(f'/api/projects/{world["project_a"].id}/').status_code == 200
        assert annotator.get(f'/api/projects/{world["project_b"].id}/').status_code in HIDDEN

    def test_task_of_foreign_project_hidden(self, world):
        annotator = client_for(world['people']['annotator'])
        assert annotator.get(f'/api/tasks/{world["task_a"].id}/').status_code == 200
        assert annotator.get(f'/api/tasks/{world["task_b"].id}/').status_code in HIDDEN

    def test_task_list_of_foreign_project_hidden(self, world):
        response = client_for(world['people']['annotator']).get('/api/tasks/', {'project': world['project_b'].id})
        assert response.status_code in HIDDEN

    def test_annotation_on_foreign_project_refused(self, world):
        response = client_for(world['people']['annotator']).post(
            f'/api/tasks/{world["task_b"].id}/annotations/', {'result': [], 'lead_time': 1}, format='json'
        )
        assert response.status_code in HIDDEN


class TestProjectActions:
    def test_only_manager_changes_settings(self, world):
        url = f'/api/projects/{world["project_a"].id}/'
        for name, expected in (('manager', 200), ('reviewer', 403), ('annotator', 403)):
            response = client_for(world['people'][name]).patch(url, {'title': f'by {name}'}, format='json')
            assert response.status_code == expected, name

    def test_only_admin_creates_projects(self, world):
        payload = {'title': 'new', 'label_config': LABEL_CONFIG}
        assert client_for(world['people']['manager']).post('/api/projects/', payload, format='json').status_code == 403
        assert client_for(world['people']['admin']).post('/api/projects/', payload, format='json').status_code == 201

    def test_only_admin_deletes_projects(self, world):
        url = f'/api/projects/{world["project_a"].id}/'
        assert client_for(world['people']['manager']).delete(url).status_code == 403
        assert client_for(world['people']['admin']).delete(url).status_code == 204
        assert not Project.objects.filter(pk=world['project_a'].id).exists()

    def test_only_manager_imports(self, world):
        url = f'/api/projects/{world["project_a"].id}/import'
        payload = [{'data': {'text': 'imported'}}]
        assert client_for(world['people']['reviewer']).post(url, payload, format='json').status_code == 403
        assert client_for(world['people']['manager']).post(url, payload, format='json').status_code == 201

    def test_only_manager_exports(self, world):
        url = f'/api/projects/{world["project_a"].id}/export'
        assert client_for(world['people']['reviewer']).get(url, {'exportType': 'JSON'}).status_code == 403
        assert client_for(world['people']['manager']).get(url, {'exportType': 'JSON'}).status_code == 200

    def test_data_manager_actions_reserved_to_manager(self, world):
        response = client_for(world['people']['annotator']).post(
            f'/api/dm/actions?id=delete_tasks&project={world["project_a"].id}',
            {'selectedItems': {'all': False, 'included': [world['task_a'].id]}},
            format='json',
        )
        assert response.status_code == 403

    def test_storages_reserved_to_manager(self, world):
        response = client_for(world['people']['annotator']).get(
            '/api/storages/s3/', {'project': world['project_a'].id}
        )
        assert response.status_code == 403


class TestAnnotationOwnership:
    def test_annotator_creates_annotation(self, world):
        response = client_for(world['people']['annotator']).post(
            f'/api/tasks/{world["task_a"].id}/annotations/', {'result': [], 'lead_time': 1}, format='json'
        )
        assert response.status_code == 201

    def test_annotator_edits_own_annotation_only(self, world):
        annotator = client_for(world['people']['annotator'])
        own = f'/api/annotations/{world["annotation_by_annotator"].id}/'
        other = f'/api/annotations/{world["annotation_by_reviewer"].id}/'
        assert annotator.patch(own, {'lead_time': 2}, format='json').status_code == 200
        assert annotator.patch(other, {'lead_time': 2}, format='json').status_code == 403
        assert annotator.delete(other).status_code == 403

    def test_reviewer_edits_any_annotation(self, world):
        url = f'/api/annotations/{world["annotation_by_annotator"].id}/'
        assert client_for(world['people']['reviewer']).patch(url, {'lead_time': 3}, format='json').status_code == 200


class TestRoleAssignmentAPI:
    def roles_url(self, world):
        return f'/api/projects/{world["project_a"].id}/roles/'

    def test_manager_grants_access(self, world):
        outsider = world['people']['outsider']
        response = client_for(world['people']['manager']).post(
            self.roles_url(world), {'user': outsider.id, 'role': Role.ANNOTATOR}, format='json'
        )
        assert response.status_code == 201
        assert listed_project_ids(outsider) == {world['project_a'].id}

    def test_reassigning_replaces_role(self, world):
        annotator = world['people']['annotator']
        response = client_for(world['people']['admin']).post(
            self.roles_url(world), {'user': annotator.id, 'role': Role.REVIEWER}, format='json'
        )
        assert response.status_code == 200
        assert ProjectRole.objects.get(project=world['project_a'], user=annotator).role == Role.REVIEWER

    def test_non_manager_cannot_manage_roles(self, world):
        reviewer = client_for(world['people']['reviewer'])
        assert reviewer.get(self.roles_url(world)).status_code == 403
        response = reviewer.post(
            self.roles_url(world), {'user': world['people']['outsider'].id, 'role': Role.MANAGER}, format='json'
        )
        assert response.status_code == 403

    def test_manager_of_one_project_cannot_manage_another(self, world):
        response = client_for(world['people']['manager']).get(f'/api/projects/{world["project_b"].id}/roles/')
        assert response.status_code in HIDDEN

    def test_user_outside_organization_rejected(self, world):
        stranger = UserFactory(active_organization=OrganizationFactory())
        response = client_for(world['people']['manager']).post(
            self.roles_url(world), {'user': stranger.id, 'role': Role.ANNOTATOR}, format='json'
        )
        assert response.status_code == 400

    def test_revoking_role_hides_project(self, world):
        annotator = world['people']['annotator']
        response = client_for(world['people']['manager']).delete(f'{self.roles_url(world)}{annotator.id}/')
        assert response.status_code == 204
        assert listed_project_ids(annotator) == set()

    def test_deleted_org_member_rejected(self, world):
        outsider = world['people']['outsider']
        OrganizationMember.objects.filter(user=outsider).update(deleted_at='2026-01-01T00:00:00Z')
        response = client_for(world['people']['manager']).post(
            self.roles_url(world), {'user': outsider.id, 'role': Role.ANNOTATOR}, format='json'
        )
        assert response.status_code == 400


class TestWebhooks:
    @pytest.fixture
    def webhooks(self, world):
        from webhooks.models import Webhook

        organization = world['organization']
        return {
            'project_a': Webhook.objects.create(
                organization=organization, project=world['project_a'], url='https://example.org/a'
            ),
            'organization': Webhook.objects.create(organization=organization, url='https://example.org/org'),
        }

    def listed_webhook_ids(self, user):
        response = client_for(user).get('/api/webhooks/')
        assert response.status_code == 200
        return {webhook['id'] for webhook in response.json()}

    def test_manager_sees_only_project_webhooks(self, world, webhooks):
        assert self.listed_webhook_ids(world['people']['manager']) == {webhooks['project_a'].id}

    def test_reviewer_sees_no_webhook(self, world, webhooks):
        assert client_for(world['people']['reviewer']).get('/api/webhooks/').status_code == 403
        response = client_for(world['people']['reviewer']).get(f'/api/webhooks/{webhooks["project_a"].id}/')
        assert response.status_code in HIDDEN

    def test_organization_webhook_reserved_to_admin(self, world, webhooks):
        url = f'/api/webhooks/{webhooks["organization"].id}/'
        assert client_for(world['people']['manager']).get(url).status_code in HIDDEN
        assert client_for(world['people']['admin']).get(url).status_code == 200

    def test_reviewer_cannot_create_webhook(self, world):
        response = client_for(world['people']['reviewer']).post(
            '/api/webhooks/', {'project': world['project_a'].id, 'url': 'https://example.org/x'}, format='json'
        )
        assert response.status_code == 403


class TestProjectResolution:
    """The view-level gate judges every project a request names, and refuses unknown references."""

    def test_query_and_body_naming_different_projects_refused(self, world):
        response = client_for(world['people']['manager']).post(
            f'/api/storages/s3/?project={world["project_a"].id}',
            {'project': world['project_b'].id, 'bucket': 'x'},
            format='json',
        )
        assert response.status_code == 403

    def test_annotator_cannot_create_prediction_through_task(self, world):
        response = client_for(world['people']['annotator']).post(
            '/api/predictions/', {'task': world['task_a'].id, 'result': [], 'score': 0.5}, format='json'
        )
        assert response.status_code == 403

    def test_unknown_project_refused(self, world):
        response = client_for(world['people']['manager']).post(
            '/api/storages/s3/', {'project': 999999, 'bucket': 'x'}, format='json'
        )
        assert response.status_code == 403

    def test_outsider_without_role_cannot_reach_manager_endpoint_without_project(self, world):
        assert client_for(world['people']['outsider']).get('/api/storages/s3/').status_code == 403
