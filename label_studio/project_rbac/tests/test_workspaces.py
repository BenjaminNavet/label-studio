"""Security tests for workspaces (ADR 0004): inherited roles, workspace rules, project placement."""

import pytest
from organizations.tests.factories import OrganizationFactory
from project_rbac.models import ProjectRole, Role, Workspace, WorkspaceProject, WorkspaceRole
from project_rbac.roles import MANAGERS, ROLE_MATRIX
from projects.models import Project, ProjectMember
from rest_framework.test import APIClient
from tasks.tests.factories import AnnotationFactory, TaskFactory
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


def listed_project_ids(user, **params):
    response = client_for(user).get('/api/projects/', {'page_size': 100, **params})
    assert response.status_code == 200
    return {project['id'] for project in response.json()['results']}


def listed_workspace_ids(user):
    response = client_for(user).get('/api/workspaces/')
    assert response.status_code == 200
    return {workspace['id'] for workspace in response.json()}


def create_project(owner, title):
    response = client_for(owner).post('/api/projects/', {'title': title, 'label_config': LABEL_CONFIG}, format='json')
    assert response.status_code == 201, response.content
    return Project.objects.get(pk=response.json()['id'])


def place(user, project, workspace):
    """Move ``project`` into ``workspace`` (or out of any when None) as ``user``."""
    body = {'workspace': workspace.id if workspace is not None else None}
    return client_for(user).patch(f'/api/projects/{project.id}/workspace/', body, format='json')


@pytest.fixture
def team():
    """One organization and one workspace owned by Alice.

    Bob manages the workspace, Carol reviews in it, Dave annotates in it, Erin is outside. Alice's
    project sits in the workspace; Bob's project and Erin's project sit in none.
    """
    organization = OrganizationFactory()
    people = {'admin': organization.created_by}
    for name in ('alice', 'bob', 'carol', 'dave', 'erin'):
        people[name] = UserFactory(active_organization=organization, email=f'{name}@lab.test')

    response = client_for(people['alice']).post('/api/workspaces/', {'title': 'Metabolomics'}, format='json')
    assert response.status_code == 201, response.content
    workspace = Workspace.objects.get(pk=response.json()['id'])
    for name, role in (('bob', Role.MANAGER), ('carol', Role.REVIEWER), ('dave', Role.ANNOTATOR)):
        workspace.grant(people[name], role)

    alice_project = create_project(people['alice'], 'alice project')
    assert place(people['alice'], alice_project, workspace).status_code == 200
    task = TaskFactory(project=alice_project, data={'text': 'a'})
    return {
        'organization': organization,
        'people': people,
        'workspace': workspace,
        'alice_project': alice_project,
        'bob_project': create_project(people['bob'], 'bob project'),
        'erin_project': create_project(people['erin'], 'erin project'),
        'task': task,
        'annotation_by_alice': AnnotationFactory(task=task, completed_by=people['alice']),
    }


def workspace_url(team, suffix=''):
    return f'/api/workspaces/{team["workspace"].id}/{suffix}'


class TestWorkspaceCrud:
    def test_any_member_creates_a_workspace_and_owns_it(self, team):
        erin = team['people']['erin']
        response = client_for(erin).post(
            '/api/workspaces/', {'title': '  Lipids  ', 'color': '#617ADA'}, format='json'
        )
        assert response.status_code == 201
        created = response.json()
        assert created['title'] == 'Lipids'
        assert (created['is_owner'], created['role']) == (True, 'manager')
        assert (created['can_manage'], created['can_delete'], created['project_count']) == (True, True, 0)
        assert WorkspaceRole.objects.get(workspace_id=created['id'], user=erin).role == Role.MANAGER

    def test_anonymous_is_refused(self, team):
        anonymous = APIClient()
        assert anonymous.get('/api/workspaces/').status_code == 401
        assert anonymous.post('/api/workspaces/', {'title': 'x'}, format='json').status_code == 401
        assert anonymous.get(workspace_url(team, 'roles/')).status_code == 401
        assert anonymous.get(f'/api/projects/{team["alice_project"].id}/workspace/').status_code == 401

    def test_title_and_color_are_validated(self, team):
        alice = client_for(team['people']['alice'])
        assert alice.post('/api/workspaces/', {'title': '   '}, format='json').status_code == 400
        assert alice.post('/api/workspaces/', {'title': 'x', 'color': 'red'}, format='json').status_code == 400

    def test_member_lists_only_their_workspaces(self, team):
        people, workspace_id = team['people'], team['workspace'].id
        assert listed_workspace_ids(people['carol']) == {workspace_id}
        assert listed_workspace_ids(people['erin']) == set()
        assert client_for(people['erin']).get(workspace_url(team)).status_code == 404

    def test_admin_sees_and_manages_every_workspace(self, team):
        response = client_for(team['people']['admin']).get(workspace_url(team))
        assert response.status_code == 200
        described = response.json()
        assert (described['role'], described['can_manage'], described['can_delete']) == (None, True, True)
        assert described['project_count'] == 1

    def test_workspace_of_another_organization_is_hidden(self, team):
        stranger = OrganizationFactory().created_by
        assert listed_workspace_ids(stranger) == set()
        assert client_for(stranger).get(workspace_url(team)).status_code == 404

    def test_only_managers_rename(self, team):
        people = team['people']
        assert client_for(people['carol']).patch(workspace_url(team), {'title': 'x'}, format='json').status_code == 403
        assert client_for(people['erin']).patch(workspace_url(team), {'title': 'x'}, format='json').status_code == 404
        response = client_for(people['bob']).patch(workspace_url(team), {'title': 'Renamed'}, format='json')
        assert response.status_code == 200
        assert response.json()['title'] == 'Renamed'

    def test_only_owner_or_admin_deletes_and_projects_survive(self, team):
        people, project = team['people'], team['alice_project']
        assert client_for(people['bob']).delete(workspace_url(team)).status_code == 403
        assert client_for(people['alice']).delete(workspace_url(team)).status_code == 204
        assert Project.objects.filter(pk=project.id).exists()
        assert not WorkspaceProject.objects.filter(project=project).exists()
        assert project.id not in listed_project_ids(people['carol'])
        assert project.id in listed_project_ids(people['alice'])


class TestWorkspaceRoles:
    def test_manager_invites_by_email_and_replaces_a_role(self, team):
        bob = client_for(team['people']['bob'])
        url = workspace_url(team, 'roles/')
        created = bob.post(url, {'email': 'ERIN@lab.test', 'role': 'annotator'}, format='json')
        assert created.status_code == 201
        assert created.json()['email'] == 'erin@lab.test'
        replaced = bob.post(url, {'user': team['people']['erin'].id, 'role': 'reviewer'}, format='json')
        assert replaced.status_code == 200
        assert WorkspaceRole.objects.get(workspace=team['workspace'], user=team['people']['erin']).role == 'reviewer'

    def test_unknown_email_refused(self, team):
        response = client_for(team['people']['alice']).post(
            workspace_url(team, 'roles/'), {'email': 'nobody@lab.test', 'role': 'annotator'}, format='json'
        )
        assert response.status_code == 400

    def test_listing_names_the_owner(self, team):
        response = client_for(team['people']['bob']).get(workspace_url(team, 'roles/'))
        assert response.status_code == 200
        roles = {row['email']: (row['role'], row['is_owner']) for row in response.json()}
        assert roles == {
            'alice@lab.test': ('manager', True),
            'bob@lab.test': ('manager', False),
            'carol@lab.test': ('reviewer', False),
            'dave@lab.test': ('annotator', False),
        }

    def test_owner_role_cannot_be_changed_or_revoked(self, team):
        bob, alice = client_for(team['people']['bob']), team['people']['alice']
        url = workspace_url(team, 'roles/')
        assert bob.post(url, {'user': alice.id, 'role': 'reviewer'}, format='json').status_code == 400
        assert bob.delete(f'{url}{alice.id}/').status_code == 400
        assert WorkspaceRole.objects.get(workspace=team['workspace'], user=alice).role == Role.MANAGER

    def test_non_manager_cannot_manage_members(self, team):
        people = team['people']
        url = workspace_url(team, 'roles/')
        carol = client_for(people['carol'])
        assert carol.get(url).status_code == 403
        assert carol.post(url, {'email': 'erin@lab.test', 'role': 'annotator'}, format='json').status_code == 403
        assert carol.delete(f'{url}{people["dave"].id}/').status_code == 403
        assert client_for(people['erin']).get(url).status_code == 404
        assert not WorkspaceRole.objects.filter(workspace=team['workspace'], user=people['erin']).exists()


class TestProjectPlacement:
    def test_owner_who_manages_the_workspace_places_the_project(self, team):
        bob, project = team['people']['bob'], team['bob_project']
        response = place(bob, project, team['workspace'])
        assert response.status_code == 200
        assert response.json() == {
            'workspace': {'id': team['workspace'].id, 'title': 'Metabolomics', 'color': '#FDFDFC'},
            'can_change': True,
        }
        assert project.id in listed_project_ids(team['people']['carol'])

    def test_owner_who_does_not_manage_the_workspace_is_refused(self, team):
        carol = team['people']['carol']
        carol_project = create_project(carol, 'carol project')
        assert place(carol, carol_project, team['workspace']).status_code == 403
        assert not WorkspaceProject.objects.filter(project=carol_project).exists()

    def test_workspace_manager_who_does_not_own_the_project_is_refused(self, team):
        bob, project = team['people']['bob'], team['erin_project']
        # Hidden from Bob: not even a refusal.
        assert place(bob, project, team['workspace']).status_code == 404
        # A direct manager role is still not ownership.
        ProjectRole.objects.create(project=project, user=bob, role=Role.MANAGER)
        assert place(bob, project, team['workspace']).status_code == 403
        assert not WorkspaceProject.objects.filter(project=project).exists()

    def test_workspace_the_user_cannot_see_is_refused(self, team):
        erin = team['people']['erin']
        hidden_workspace = Workspace.objects.create(
            organization=team['organization'], title='Private', created_by=team['people']['carol']
        )
        assert place(erin, team['erin_project'], hidden_workspace).status_code == 400
        response = client_for(erin).patch(
            f'/api/projects/{team["erin_project"].id}/workspace/', {'workspace': 'x'}, format='json'
        )
        assert response.status_code == 400
        assert (
            client_for(erin)
            .patch(f'/api/projects/{team["erin_project"].id}/workspace/', {}, format='json')
            .status_code
            == 400
        )

    def test_admin_places_any_project(self, team):
        assert place(team['people']['admin'], team['erin_project'], team['workspace']).status_code == 200
        assert WorkspaceProject.objects.get(project=team['erin_project']).workspace_id == team['workspace'].id

    def test_detach_by_project_owner_or_workspace_manager(self, team):
        people, project = team['people'], team['alice_project']
        assert place(people['carol'], project, None).status_code == 403
        assert WorkspaceProject.objects.filter(project=project).exists()
        # Bob manages the workspace without owning the project.
        response = place(people['bob'], project, None)
        assert response.status_code == 200
        assert response.json()['workspace'] is None
        assert place(people['alice'], project, team['workspace']).status_code == 200
        assert place(people['alice'], project, None).status_code == 200
        assert not WorkspaceProject.objects.filter(project=project).exists()

    def test_reader_sees_the_workspace_name_but_cannot_change_it(self, team):
        response = client_for(team['people']['dave']).get(f'/api/projects/{team["alice_project"].id}/workspace/')
        assert response.status_code == 200
        assert response.json()['workspace']['title'] == 'Metabolomics'
        assert response.json()['can_change'] is False
        hidden = client_for(team['people']['erin']).get(f'/api/projects/{team["alice_project"].id}/workspace/')
        assert hidden.status_code in HIDDEN

    def test_list_filter_by_workspace(self, team):
        alice, workspace_id = team['people']['alice'], team['workspace'].id
        other_project = create_project(alice, 'outside')
        assert listed_project_ids(alice, workspace=workspace_id) == {team['alice_project'].id}
        assert listed_project_ids(alice, workspace='none') == {other_project.id}
        assert listed_project_ids(alice, workspace='garbage') == set()
        # The filter narrows what the user sees; it never widens it.
        assert listed_project_ids(team['people']['erin'], workspace=workspace_id) == set()

    def test_placing_a_project_registers_members_for_the_data_manager(self, team):
        project, carol = team['bob_project'], team['people']['carol']
        assert not ProjectMember.objects.filter(project=project, user=carol).exists()
        assert place(team['people']['bob'], project, team['workspace']).status_code == 200
        assert ProjectMember.objects.filter(project=project, user=carol).exists()


class TestInheritedRoles:
    def test_role_sets_are_upward_closed(self):
        """ADR 0004 relies on this to filter listings with a union instead of comparing roles."""
        order = [Role.ANNOTATOR, Role.REVIEWER, Role.MANAGER]
        for permission, roles in {**ROLE_MATRIX, 'unlisted': MANAGERS}.items():
            lowest = min(order.index(role) for role in roles)
            assert set(roles) == set(order[lowest:]), permission

    def test_workspace_member_sees_and_acts_on_its_projects(self, team):
        people, project = team['people'], team['alice_project']
        for name in ('bob', 'carol', 'dave'):
            assert listed_project_ids(people[name]) >= {project.id}, name
            assert client_for(people[name]).get(f'/api/projects/{project.id}/').status_code == 200, name
        assert project.id not in listed_project_ids(people['erin'])
        assert client_for(people['erin']).get(f'/api/projects/{project.id}/').status_code in HIDDEN

        created = client_for(people['dave']).post(
            f'/api/tasks/{team["task"].id}/annotations/', {'result': [], 'lead_time': 1}, format='json'
        )
        assert created.status_code == 201

    def test_inherited_role_follows_the_matrix(self, team):
        people = team['people']
        settings_url = f'/api/projects/{team["alice_project"].id}/'
        annotation_url = f'/api/annotations/{team["annotation_by_alice"].id}/'
        for name, expected in (('bob', 200), ('carol', 403), ('dave', 403)):
            response = client_for(people[name]).patch(settings_url, {'description': name}, format='json')
            assert response.status_code == expected, name
        for name, expected in (('carol', 200), ('dave', 403)):
            response = client_for(people[name]).patch(annotation_url, {'lead_time': 2}, format='json')
            assert response.status_code == expected, name

    def test_effective_role_is_the_highest(self, team):
        people, project = team['people'], team['alice_project']
        annotation_url = f'/api/annotations/{team["annotation_by_alice"].id}/'
        # Annotator through the workspace, reviewer on the project itself.
        ProjectRole.objects.create(project=project, user=people['dave'], role=Role.REVIEWER)
        assert client_for(people['dave']).patch(annotation_url, {'lead_time': 3}, format='json').status_code == 200
        # Reviewer through the workspace, annotator on the project itself.
        ProjectRole.objects.create(project=project, user=people['carol'], role=Role.ANNOTATOR)
        assert client_for(people['carol']).patch(annotation_url, {'lead_time': 4}, format='json').status_code == 200

    def test_revoking_a_workspace_role_removes_inherited_access(self, team):
        people, project = team['people'], team['alice_project']
        response = client_for(people['alice']).delete(workspace_url(team, f'roles/{people["carol"].id}/'))
        assert response.status_code == 204
        assert project.id not in listed_project_ids(people['carol'])
        assert client_for(people['carol']).get(f'/api/projects/{project.id}/').status_code in HIDDEN
        assert client_for(people['carol']).get(f'/api/tasks/{team["task"].id}/').status_code in HIDDEN

    def test_detaching_removes_inherited_access_and_keeps_direct_roles(self, team):
        people, project = team['people'], team['alice_project']
        ProjectRole.objects.create(project=project, user=people['dave'], role=Role.ANNOTATOR)
        assert place(people['alice'], project, None).status_code == 200
        assert project.id not in listed_project_ids(people['carol'])
        assert project.id in listed_project_ids(people['dave'])

    def test_inherited_manager_cannot_delete_project(self, team):
        people, project = team['people'], team['alice_project']
        assert client_for(people['bob']).delete(f'/api/projects/{project.id}/').status_code == 403
        assert Project.objects.filter(pk=project.id).exists()

    def test_project_members_listing_shows_inherited_members(self, team):
        people, project = team['people'], team['alice_project']
        ProjectRole.objects.create(project=project, user=people['erin'], role=Role.ANNOTATOR)
        response = client_for(people['alice']).get(f'/api/projects/{project.id}/roles/')
        assert response.status_code == 200
        roles = {row['email']: (row['role'], row['workspace_role']) for row in response.json()}
        assert roles == {
            'alice@lab.test': ('manager', 'manager'),
            'bob@lab.test': (None, 'manager'),
            'carol@lab.test': (None, 'reviewer'),
            'dave@lab.test': (None, 'annotator'),
            'erin@lab.test': ('annotator', None),
        }
        # An inherited member is removed from the workspace, not from the project.
        removal = client_for(people['alice']).delete(f'/api/projects/{project.id}/roles/{people["carol"].id}/')
        assert removal.status_code == 404

    def test_inherited_manager_manages_project_members(self, team):
        people, project = team['people'], team['alice_project']
        response = client_for(people['bob']).post(
            f'/api/projects/{project.id}/roles/', {'email': 'erin@lab.test', 'role': 'annotator'}, format='json'
        )
        assert response.status_code == 201
        assert response.json()['workspace_role'] is None
        refused = client_for(people['carol']).get(f'/api/projects/{project.id}/roles/')
        assert refused.status_code == 403

    def test_workspace_members_are_teammates(self, team):
        people = team['people']

        def listed_user_ids(user):
            response = client_for(user).get('/api/users/')
            assert response.status_code == 200
            return {listed['id'] for listed in response.json()}

        workspace_member_ids = {people[name].id for name in ('alice', 'bob', 'carol', 'dave')}
        assert listed_user_ids(people['dave']) == workspace_member_ids
        assert listed_user_ids(people['erin']) == {people['erin'].id}

    def test_inherited_manager_sees_project_webhooks(self, team):
        from webhooks.models import Webhook

        webhook = Webhook.objects.create(
            organization=team['organization'], project=team['alice_project'], url='https://example.org/a'
        )
        response = client_for(team['people']['bob']).get('/api/webhooks/')
        assert response.status_code == 200
        assert {listed['id'] for listed in response.json()} == {webhook.id}
        assert client_for(team['people']['carol']).get('/api/webhooks/').status_code == 403
