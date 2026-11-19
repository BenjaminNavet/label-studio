"""Security tests for project ownership (ADR 0002): creation by members, owner role, deletion, invitation."""

import importlib

import pytest
from django.apps import apps
from organizations.tests.factories import OrganizationFactory
from project_rbac.models import ProjectRole, Role
from projects.models import Project
from rest_framework.test import APIClient
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HIDDEN = (403, 404)
LABEL_CONFIG = (
    '<View><Text name="text" value="$text"/>'
    '<Choices name="label" toName="text"><Choice value="a"/><Choice value="b"/></Choices></View>'
)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def listed_project_ids(user):
    response = client_for(user).get('/api/projects/', {'page_size': 100})
    assert response.status_code == 200
    return {project['id'] for project in response.json()['results']}


@pytest.fixture
def lab():
    """One organization; Alice creates a project through the API, Bob and Carol are plain members."""
    organization = OrganizationFactory()
    people = {'admin': organization.created_by}
    for name in ('alice', 'bob', 'carol'):
        people[name] = UserFactory(active_organization=organization, email=f'{name}@lab.test')
    response = client_for(people['alice']).post(
        '/api/projects/', {'title': 'alice project', 'label_config': LABEL_CONFIG}, format='json'
    )
    assert response.status_code == 201, response.content
    project = Project.objects.get(pk=response.json()['id'])
    return {'organization': organization, 'people': people, 'project': project}


def roles_url(lab, user=None):
    url = f'/api/projects/{lab["project"].id}/roles/'
    return url if user is None else f'{url}{user.id}/'


def invite(lab, inviter, email, role):
    return client_for(lab['people'][inviter]).post(roles_url(lab), {'email': email, 'role': role}, format='json')


class TestCreation:
    def test_member_creates_project_and_becomes_its_manager(self, lab):
        alice = lab['people']['alice']
        assert lab['project'].created_by_id == alice.id
        assert ProjectRole.objects.get(project=lab['project'], user=alice).role == Role.MANAGER

    def test_project_is_private_to_its_owner(self, lab):
        assert listed_project_ids(lab['people']['alice']) == {lab['project'].id}
        assert listed_project_ids(lab['people']['bob']) == set()
        assert client_for(lab['people']['bob']).get(f'/api/projects/{lab["project"].id}/').status_code in HIDDEN

    def test_admin_sees_every_project(self, lab):
        assert lab['project'].id in listed_project_ids(lab['people']['admin'])

    def test_owner_configures_and_imports(self, lab):
        alice = client_for(lab['people']['alice'])
        url = f'/api/projects/{lab["project"].id}/'
        assert alice.patch(url, {'title': 'renamed'}, format='json').status_code == 200
        assert alice.post(f'{url}import', [{'data': {'text': 'one'}}], format='json').status_code == 201

    def test_creation_naming_a_foreign_project_is_refused(self, lab):
        response = client_for(lab['people']['bob']).post(
            f'/api/projects/?project={lab["project"].id}', {'title': 'x', 'label_config': LABEL_CONFIG}, format='json'
        )
        assert response.status_code == 403


class TestDeletion:
    def test_owner_deletes_own_project(self, lab):
        response = client_for(lab['people']['alice']).delete(f'/api/projects/{lab["project"].id}/')
        assert response.status_code == 204
        assert not Project.objects.filter(pk=lab['project'].id).exists()

    def test_invited_manager_cannot_delete(self, lab):
        assert invite(lab, 'alice', 'bob@lab.test', 'manager').status_code == 201
        response = client_for(lab['people']['bob']).delete(f'/api/projects/{lab["project"].id}/')
        assert response.status_code == 403
        assert Project.objects.filter(pk=lab['project'].id).exists()

    def test_stranger_cannot_delete(self, lab):
        response = client_for(lab['people']['bob']).delete(f'/api/projects/{lab["project"].id}/')
        assert response.status_code in HIDDEN
        assert Project.objects.filter(pk=lab['project'].id).exists()

    def test_admin_deletes_any_project(self, lab):
        assert client_for(lab['people']['admin']).delete(f'/api/projects/{lab["project"].id}/').status_code == 204


class TestInvitation:
    def test_owner_invites_by_email(self, lab):
        response = invite(lab, 'alice', 'Bob@Lab.test', 'annotator')
        assert response.status_code == 201, response.content
        assert response.json()['user'] == lab['people']['bob'].id
        assert listed_project_ids(lab['people']['bob']) == {lab['project'].id}
        assert listed_project_ids(lab['people']['carol']) == set()

    def test_unknown_email_refused(self, lab):
        response = invite(lab, 'alice', 'nobody@lab.test', 'annotator')
        assert response.status_code == 400
        assert not ProjectRole.objects.filter(project=lab['project']).exclude(user=lab['people']['alice']).exists()

    def test_deactivated_account_refused(self, lab):
        bob = lab['people']['bob']
        bob.is_active = False
        bob.save(update_fields=['is_active'])
        assert invite(lab, 'alice', 'bob@lab.test', 'annotator').status_code == 400

    def test_missing_member_refused(self, lab):
        response = client_for(lab['people']['alice']).post(roles_url(lab), {'role': 'annotator'}, format='json')
        assert response.status_code == 400

    def test_annotator_cannot_invite(self, lab):
        assert invite(lab, 'alice', 'bob@lab.test', 'annotator').status_code == 201
        assert invite(lab, 'bob', 'carol@lab.test', 'annotator').status_code == 403
        assert listed_project_ids(lab['people']['carol']) == set()

    def test_stranger_cannot_invite_themselves(self, lab):
        assert invite(lab, 'bob', 'bob@lab.test', 'manager').status_code in HIDDEN
        assert listed_project_ids(lab['people']['bob']) == set()

    def test_revoked_member_loses_access(self, lab):
        bob = lab['people']['bob']
        assert invite(lab, 'alice', 'bob@lab.test', 'reviewer').status_code == 201
        assert client_for(lab['people']['alice']).delete(roles_url(lab, bob)).status_code == 204
        assert listed_project_ids(bob) == set()

    def test_listing_names_members_and_flags_the_owner(self, lab):
        assert invite(lab, 'alice', 'bob@lab.test', 'reviewer').status_code == 201
        response = client_for(lab['people']['alice']).get(roles_url(lab))
        assert response.status_code == 200
        rows = {row['email']: row for row in response.json()}
        assert rows['alice@lab.test']['is_owner'] is True
        assert rows['alice@lab.test']['role'] == 'manager'
        assert rows['bob@lab.test']['is_owner'] is False
        assert rows['bob@lab.test']['role'] == 'reviewer'
        assert {'first_name', 'last_name', 'user'} <= set(rows['bob@lab.test'])


class TestOwnerIsProtected:
    @pytest.fixture
    def with_second_manager(self, lab):
        assert invite(lab, 'alice', 'bob@lab.test', 'manager').status_code == 201
        return lab

    def test_owner_cannot_be_demoted(self, with_second_manager):
        lab = with_second_manager
        assert invite(lab, 'bob', 'alice@lab.test', 'annotator').status_code == 400
        assert ProjectRole.objects.get(project=lab['project'], user=lab['people']['alice']).role == Role.MANAGER

    def test_owner_cannot_be_removed(self, with_second_manager):
        lab = with_second_manager
        response = client_for(lab['people']['bob']).delete(roles_url(lab, lab['people']['alice']))
        assert response.status_code == 400
        assert ProjectRole.objects.filter(project=lab['project'], user=lab['people']['alice']).exists()

    def test_ownership_cannot_be_taken_through_project_update(self, with_second_manager):
        lab = with_second_manager
        bob = lab['people']['bob']
        for payload in ({'created_by': bob.id}, {'created_by': {'id': bob.id}}, {'created_by_id': bob.id}):
            client_for(bob).patch(f'/api/projects/{lab["project"].id}/', payload, format='json')
            lab['project'].refresh_from_db()
            assert lab['project'].created_by_id == lab['people']['alice'].id, payload


def test_data_migration_grants_manager_role_to_existing_owners(lab):
    alice = lab['people']['alice']
    ProjectRole.objects.filter(project=lab['project']).delete()
    migration = importlib.import_module('project_rbac.migrations.0002_owner_is_manager')

    migration.grant_manager_role_to_owners(apps, None)

    assert ProjectRole.objects.get(project=lab['project'], user=alice).role == Role.MANAGER
