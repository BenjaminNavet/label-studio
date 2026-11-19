"""Security tests for account administration (ADR 0003)."""

import pytest
from django.contrib.auth import authenticate
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from project_rbac.models import ProjectRole, Role
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from users.models import User
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

ACCOUNTS = '/api/rbac/accounts/'


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def lab():
    """An organization owner, a second administrator, and members Alice, Bob (same project) and Carol (alone)."""
    organization = OrganizationFactory()
    people = {'owner': organization.created_by}
    for name in ('second_admin', 'alice', 'bob', 'carol'):
        people[name] = UserFactory(active_organization=organization, email=f'{name}@lab.test')
    people['second_admin'].is_superuser = True
    people['second_admin'].save(update_fields=['is_superuser'])
    project = ProjectFactory(organization=organization, created_by=people['alice'])
    ProjectRole.objects.create(project=project, user=people['bob'], role=Role.ANNOTATOR)
    return {'organization': organization, 'people': people, 'project': project}


def create_account(lab, **fields):
    payload = {'email': 'dave@lab.test', 'first_name': 'Dave', 'last_name': 'Doe', **fields}
    return client_for(lab['people']['owner']).post(ACCOUNTS, payload, format='json')


class TestWhoAmI:
    def test_administrators_are_flagged(self, lab):
        for name, expected in (('owner', True), ('second_admin', True), ('alice', False)):
            response = client_for(lab['people'][name]).get('/api/rbac/me/')
            assert response.status_code == 200
            assert response.json() == {'is_admin': expected}, name

    def test_anonymous_is_refused(self):
        assert APIClient().get('/api/rbac/me/').status_code == 401


class TestOnlyAdministratorsManageAccounts:
    def test_member_is_refused_everywhere(self, lab):
        alice = client_for(lab['people']['alice'])
        bob = lab['people']['bob']
        assert alice.get(ACCOUNTS).status_code == 403
        assert alice.post(ACCOUNTS, {'email': 'x@lab.test'}, format='json').status_code == 403
        assert alice.patch(f'{ACCOUNTS}{bob.id}/', {'is_admin': True}, format='json').status_code == 403
        assert (
            alice.patch(f'{ACCOUNTS}{lab["people"]["alice"].id}/', {'is_admin': True}, format='json').status_code
            == 403
        )
        assert alice.post(f'{ACCOUNTS}{bob.id}/reset-password/').status_code == 403
        assert not User.objects.filter(email='x@lab.test').exists()
        lab['people']['alice'].refresh_from_db()
        assert lab['people']['alice'].is_superuser is False

    def test_anonymous_is_refused(self, lab):
        assert APIClient().get(ACCOUNTS).status_code == 401
        assert APIClient().post(ACCOUNTS, {'email': 'x@lab.test'}, format='json').status_code == 401

    def test_second_administrator_manages_accounts(self, lab):
        assert client_for(lab['people']['second_admin']).get(ACCOUNTS).status_code == 200


class TestAccountLifecycle:
    def test_listing_shows_every_account_without_secrets(self, lab):
        response = client_for(lab['people']['owner']).get(ACCOUNTS)
        assert response.status_code == 200
        rows = {row['email']: row for row in response.json()}
        assert {'alice@lab.test', 'bob@lab.test', 'carol@lab.test', 'second_admin@lab.test'} <= set(rows)
        assert rows[lab['people']['owner'].email]['is_owner'] is True
        assert rows[lab['people']['owner'].email]['is_admin'] is True
        assert rows['second_admin@lab.test']['is_admin'] is True
        assert rows['alice@lab.test']['is_admin'] is False
        assert rows['alice@lab.test']['project_count'] == 1
        assert rows['carol@lab.test']['project_count'] == 0
        assert all('password' not in row for row in rows.values())

    def test_created_account_can_log_in_and_sees_nothing(self, lab):
        response = create_account(lab, email='Dave@Lab.test')
        assert response.status_code == 201, response.content
        body = response.json()
        assert body['email'] == 'dave@lab.test'
        assert len(body['password']) >= 12
        dave = authenticate(email='dave@lab.test', password=body['password'])
        assert dave is not None and dave.is_superuser is False
        assert OrganizationMember.objects.filter(user=dave, organization=lab['organization']).exists()
        projects = client_for(dave).get('/api/projects/', {'page_size': 100})
        assert projects.status_code == 200 and projects.json()['results'] == []

    def test_duplicate_email_refused(self, lab):
        assert create_account(lab, email='ALICE@lab.test').status_code == 400
        assert create_account(lab, email='not-an-email').status_code == 400
        assert create_account(lab, email='').status_code == 400

    def test_password_is_never_chosen_by_the_caller(self, lab):
        response = create_account(lab, password='chosen-by-caller')
        assert response.status_code == 201
        assert authenticate(email='dave@lab.test', password='chosen-by-caller') is None

    def test_reset_password_replaces_the_old_one(self, lab):
        old_password = create_account(lab).json()['password']
        dave = User.objects.get(email='dave@lab.test')
        response = client_for(lab['people']['owner']).post(f'{ACCOUNTS}{dave.id}/reset-password/')
        assert response.status_code == 200
        new_password = response.json()['password']
        assert new_password != old_password
        assert authenticate(email='dave@lab.test', password=old_password) is None
        assert authenticate(email='dave@lab.test', password=new_password) is not None

    def test_deactivated_account_cannot_log_in_nor_use_the_api(self, lab):
        password = create_account(lab).json()['password']
        dave = User.objects.get(email='dave@lab.test')
        session_client = APIClient()
        # Through the real login form: it sets the session keys the session-timeout middleware expects.
        session_client.post('/user/login/', {'email': 'dave@lab.test', 'password': password})
        assert session_client.get('/api/projects/').status_code == 200

        response = client_for(lab['people']['owner']).patch(
            f'{ACCOUNTS}{dave.id}/', {'is_active': False}, format='json'
        )

        assert response.status_code == 200 and response.json()['is_active'] is False
        assert authenticate(email='dave@lab.test', password=password) is None
        assert session_client.get('/api/projects/').status_code == 401

        client_for(lab['people']['owner']).patch(f'{ACCOUNTS}{dave.id}/', {'is_active': True}, format='json')
        assert authenticate(email='dave@lab.test', password=password) is not None

    def test_promotion_gives_access_to_account_administration(self, lab):
        alice = lab['people']['alice']
        response = client_for(lab['people']['owner']).patch(
            f'{ACCOUNTS}{alice.id}/', {'is_admin': True}, format='json'
        )
        assert response.status_code == 200 and response.json()['is_admin'] is True
        alice.refresh_from_db()
        assert client_for(alice).get(ACCOUNTS).status_code == 200

    def test_update_changes_name_and_email(self, lab):
        alice = lab['people']['alice']
        payload = {'first_name': 'Alicia', 'last_name': 'Liddell', 'email': 'Alicia@lab.test'}
        response = client_for(lab['people']['owner']).patch(f'{ACCOUNTS}{alice.id}/', payload, format='json')
        assert response.status_code == 200, response.content
        alice.refresh_from_db()
        assert (alice.first_name, alice.last_name, alice.email) == ('Alicia', 'Liddell', 'alicia@lab.test')
        taken = client_for(lab['people']['owner']).patch(
            f'{ACCOUNTS}{alice.id}/', {'email': 'bob@lab.test'}, format='json'
        )
        assert taken.status_code == 400


class TestAdministratorsCannotLockThemselvesOut:
    def test_no_self_deactivation_or_demotion(self, lab):
        second_admin = lab['people']['second_admin']
        client = client_for(second_admin)
        assert client.patch(f'{ACCOUNTS}{second_admin.id}/', {'is_active': False}, format='json').status_code == 400
        assert client.patch(f'{ACCOUNTS}{second_admin.id}/', {'is_admin': False}, format='json').status_code == 400
        second_admin.refresh_from_db()
        assert second_admin.is_active and second_admin.is_superuser

    def test_organization_owner_stays_active(self, lab):
        owner = lab['people']['owner']
        response = client_for(lab['people']['second_admin']).patch(
            f'{ACCOUNTS}{owner.id}/', {'is_active': False}, format='json'
        )
        assert response.status_code == 400
        owner.refresh_from_db()
        assert owner.is_active

    def test_unchanged_flags_do_not_block_an_edit(self, lab):
        second_admin = lab['people']['second_admin']
        payload = {'first_name': 'Sam', 'is_admin': True, 'is_active': True}
        response = client_for(second_admin).patch(f'{ACCOUNTS}{second_admin.id}/', payload, format='json')
        assert response.status_code == 200


class TestUpstreamAccountEndpointsAreClosedToMembers:
    def test_member_cannot_create_a_user(self, lab):
        response = client_for(lab['people']['alice']).post(
            '/api/users/', {'email': 'intruder@lab.test', 'username': 'intruder'}, format='json'
        )
        assert response.status_code == 403
        assert not User.objects.filter(email='intruder@lab.test').exists()

    def test_member_cannot_edit_another_member(self, lab):
        bob = lab['people']['bob']
        response = client_for(lab['people']['alice']).patch(
            f'/api/users/{bob.id}/', {'first_name': 'Hacked'}, format='json'
        )
        assert response.status_code in (403, 404)
        bob.refresh_from_db()
        assert bob.first_name != 'Hacked'

    def test_member_edits_own_profile(self, lab):
        alice = lab['people']['alice']
        response = client_for(alice).patch(f'/api/users/{alice.id}/', {'first_name': 'Alicia'}, format='json')
        assert response.status_code == 200, response.content
        alice.refresh_from_db()
        assert alice.first_name == 'Alicia'

    def test_member_cannot_delete_a_user(self, lab):
        bob = lab['people']['bob']
        assert client_for(lab['people']['alice']).delete(f'/api/users/{bob.id}/').status_code == 403
        assert User.objects.filter(pk=bob.id).exists()

    def test_member_cannot_read_or_reset_the_invite_link(self, lab):
        alice = client_for(lab['people']['alice'])
        assert alice.get('/api/invite').status_code == 403
        assert alice.post('/api/invite/reset-token').status_code == 403
        assert client_for(lab['people']['owner']).get('/api/invite').status_code == 200

    def test_member_cannot_change_the_organization(self, lab):
        organization = lab['organization']
        response = client_for(lab['people']['alice']).patch(
            f'/api/organizations/{organization.id}', {'title': 'taken over'}, format='json'
        )
        assert response.status_code == 403

    def test_member_cannot_remove_a_member(self, lab):
        organization, bob = lab['organization'], lab['people']['bob']
        response = client_for(lab['people']['alice']).delete(
            f'/api/organizations/{organization.id}/memberships/{bob.id}/'
        )
        assert response.status_code == 403
        assert OrganizationMember.objects.get(user=bob, organization=organization).deleted_at is None


class TestUserListingsAreFiltered:
    @staticmethod
    def listed_emails(response):
        body = response.json()
        rows = body['results'] if isinstance(body, dict) else body
        return {(row.get('user') or row)['email'] for row in rows}

    def test_member_lists_only_teammates(self, lab):
        response = client_for(lab['people']['bob']).get('/api/users/')
        assert response.status_code == 200
        assert self.listed_emails(response) == {'alice@lab.test', 'bob@lab.test'}

    def test_member_without_project_lists_only_themselves(self, lab):
        response = client_for(lab['people']['carol']).get('/api/users/')
        assert self.listed_emails(response) == {'carol@lab.test'}

    def test_member_cannot_read_a_stranger(self, lab):
        carol = lab['people']['carol']
        assert client_for(lab['people']['bob']).get(f'/api/users/{carol.id}/').status_code == 404

    def test_membership_listing_is_filtered(self, lab):
        url = f'/api/organizations/{lab["organization"].id}/memberships'
        assert self.listed_emails(client_for(lab['people']['bob']).get(url)) == {'alice@lab.test', 'bob@lab.test'}

    def test_administrator_lists_everyone(self, lab):
        emails = self.listed_emails(client_for(lab['people']['owner']).get('/api/users/'))
        assert {'alice@lab.test', 'bob@lab.test', 'carol@lab.test', 'second_admin@lab.test'} <= emails
