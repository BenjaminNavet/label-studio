"""End-to-end check of workspaces (ADR 0004) on a running stack, in a headless browser.

Creates two accounts as the administrator, then plays Alice (workspace owner) and Bob (reviewer through
the workspace) in the interface and checks the outcome through the API. Run it against a fresh stack:
the accounts ``alice.ws@local.test`` and ``bob.ws@local.test`` must not exist yet.

    set -a; . ./.env; set +a
    BASE=http://localhost:$LABEL_STUDIO_PORT uv run --no-project --with playwright python check_workspaces.py

``BASE`` must use the host name of ``LABEL_STUDIO_HOST`` (``localhost``), or API calls lose their cookie.
Optional: ``HEADLESS_SHELL`` (path of a Chromium binary, when Playwright's own is not installed) and
``SCREENSHOTS`` (directory receiving a few captures).
"""

import json
import os
import re
import sys

from playwright.sync_api import expect, sync_playwright

BASE = os.environ['BASE']
ADMIN_EMAIL = os.environ['LABEL_STUDIO_USERNAME']
ADMIN_PASSWORD = os.environ['LABEL_STUDIO_PASSWORD']
HEADLESS_SHELL = os.environ.get('HEADLESS_SHELL')
SCREENSHOTS = os.environ.get('SCREENSHOTS')

results = []


def check(label, condition, detail=''):
    results.append((label, bool(condition)))
    print(
        f'{"ok  " if condition else "FAIL"} {label}{"  -> " + str(detail) if detail and not condition else ""}',
        flush=True,
    )


def shoot(page, name):
    """Save a capture of ``page`` when a ``SCREENSHOTS`` directory is given."""
    if SCREENSHOTS:
        page.screenshot(path=f'{SCREENSHOTS}/{name}.png')


def step(label, action):
    """Run an interface step; a timeout or a missing element fails the step instead of the whole run."""
    try:
        action()
        check(label, True)
    except Exception as error:
        check(label, False, str(error).splitlines()[0][:200])


def login(browser, email, password):
    context = browser.new_context(base_url=BASE, viewport={'width': 1400, 'height': 900})
    page = context.new_page()
    page.goto('/user/login')
    page.fill('#email', email)
    page.fill('#password', password)
    page.click('button[type=submit]')
    page.wait_for_url(lambda url: '/user/login' not in url)
    return context, page


def api(context, method, path, body=None):
    csrf = next((cookie['value'] for cookie in context.cookies() if cookie['name'] == 'csrftoken'), '')
    return context.request.fetch(
        BASE + path,
        method=method,
        data=json.dumps(body) if body is not None else None,
        headers={'X-CSRFToken': csrf, 'Content-Type': 'application/json', 'Referer': BASE + '/'},
    )


def choose(page, select_test_id, value):
    page.get_by_test_id(select_test_id).click()
    page.get_by_test_id(f'select-option-{value}').click()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path=HEADLESS_SHELL)

    # --- accounts, by the administrator -------------------------------------------------------------
    admin_context, admin_page = login(browser, ADMIN_EMAIL, ADMIN_PASSWORD)
    accounts = {}
    for name in ('alice', 'bob'):
        response = api(admin_context, 'POST', '/api/rbac/accounts/', {'email': f'{name}.ws@local.test'})
        check(f'admin creates the account of {name}', response.status == 201, response.text()[:200])
        accounts[name] = response.json()
    check('admin starts with no workspace', api(admin_context, 'GET', '/api/workspaces/').json() == [])

    # --- Alice creates a workspace and a project in it ----------------------------------------------
    alice_context, alice = login(browser, accounts['alice']['email'], accounts['alice']['password'])
    alice.goto('/projects')
    step(
        'sidebar is shown on the Projects page',
        lambda: expect(alice.get_by_test_id('workspaces-sidebar')).to_be_visible(),
    )

    def create_workspace():
        alice.get_by_test_id('workspace-create-button').click()
        expect(alice.get_by_test_id('workspace-title-input')).to_be_visible()
        alice.get_by_test_id('workspace-title-input').fill('Metabolomics')
        alice.get_by_test_id('workspace-save-button').click()
        expect(alice.get_by_test_id('workspaces-sidebar')).to_contain_text('Metabolomics')

    step('Alice creates a workspace from the sidebar', create_workspace)
    workspaces = api(alice_context, 'GET', '/api/workspaces/').json()
    check(
        'the workspace exists and Alice manages it',
        len(workspaces) == 1 and workspaces[0]['role'] == 'manager',
        workspaces,
    )
    workspace_id = workspaces[0]['id'] if workspaces else 0
    step(
        'the new workspace is selected and empty',
        lambda: (
            expect(alice.get_by_test_id('projects-empty-filter')).to_be_visible(),
            expect(alice).to_have_url(re.compile(rf'workspace={workspace_id}')),
        ),
    )
    shoot(alice, '1-workspace-vide')

    def create_project():
        alice.get_by_test_id('projects-empty-filter').get_by_role('button', name='Create').click()
        expect(alice.locator('#project_name')).to_be_visible()
        expect(alice.get_by_test_id('workspace-select')).to_contain_text('Metabolomics')
        shoot(alice, '2-creation-projet')
        alice.locator('#project_name').fill('Lipids')
        alice.get_by_role('button', name='Save').click()
        alice.wait_for_url(re.compile(r'/projects/\d+/data'))

    step('the creation wizard preselects the workspace and creates the project', create_project)
    match = re.search(r'/projects/(\d+)/', alice.url)
    project_id = int(match.group(1)) if match else 0
    placement = api(alice_context, 'GET', f'/api/projects/{project_id}/workspace/')
    placed = placement.status == 200 and (placement.json()['workspace'] or {}).get('id') == workspace_id
    check('the project is in the workspace', placed, placement.text()[:200])

    def filter_projects():
        alice.goto(f'/projects?workspace={workspace_id}')
        expect(alice.get_by_text('Lipids').first).to_be_visible()
        shoot(alice, '3-workspace-avec-projet')
        alice.get_by_test_id('workspace-item-none').click()
        expect(alice.get_by_test_id('projects-empty-filter')).to_be_visible()
        alice.get_by_test_id('workspace-item-all').click()
        expect(alice.get_by_text('Lipids').first).to_be_visible()

    step('the sidebar filters the project list', filter_projects)

    bob_id = accounts['bob']['id']

    def invite_bob():
        alice.get_by_test_id(f'workspace-settings-button-{workspace_id}').click()
        expect(alice.get_by_test_id('workspace-members-table')).to_be_visible()
        alice.get_by_test_id('workspace-members-email-input').fill(accounts['bob']['email'])
        choose(alice, 'workspace-members-new-role-select', 'reviewer')
        alice.get_by_test_id('workspace-members-add-button').click()
        expect(alice.get_by_test_id(f'workspace-members-row-{bob_id}')).to_be_visible()
        shoot(alice, '4-membres-workspace')

    step('Alice invites Bob as a reviewer from the workspace settings', invite_bob)
    roles = api(alice_context, 'GET', f'/api/workspaces/{workspace_id}/roles/').json()
    check(
        'Bob is a reviewer of the workspace',
        {'reviewer'} == {row['role'] for row in roles if row['user'] == bob_id},
        roles,
    )

    def inherited_member_row():
        alice.goto(f'/projects/{project_id}/settings/members')
        expect(alice.get_by_test_id(f'members-inherited-{bob_id}')).to_be_visible()
        expect(alice.get_by_test_id(f'members-remove-button-{bob_id}')).to_have_count(0)
        shoot(alice, '5-membres-projet')

    step('the project members page shows Bob as inherited, read-only', inherited_member_row)

    def settings_show_workspace():
        alice.goto(f'/projects/{project_id}/settings')
        expect(alice.get_by_test_id('workspace-select')).to_contain_text('Metabolomics')
        expect(alice.get_by_test_id('workspace-select')).to_be_enabled()
        shoot(alice, '6-reglages-projet')

    step('general settings show the workspace of the project', settings_show_workspace)

    # --- Bob, reviewer through the workspace --------------------------------------------------------
    bob_context, bob = login(browser, accounts['bob']['email'], accounts['bob']['password'])

    def bob_sees_the_workspace():
        bob.goto('/projects')
        expect(bob.get_by_test_id(f'workspace-item-{workspace_id}')).to_be_visible()
        expect(bob.get_by_text('Lipids').first).to_be_visible()
        expect(bob.get_by_test_id(f'workspace-settings-button-{workspace_id}')).to_have_count(0)

    step('Bob sees the workspace and its project, without the settings button', bob_sees_the_workspace)
    check('Bob reads the project', api(bob_context, 'GET', f'/api/projects/{project_id}/').status == 200)
    check(
        'Bob cannot change its settings',
        api(bob_context, 'PATCH', f'/api/projects/{project_id}/', {'title': 'x'}).status == 403,
    )
    check(
        'Bob cannot rename the workspace',
        api(bob_context, 'PATCH', f'/api/workspaces/{workspace_id}/', {'title': 'x'}).status == 403,
    )
    check(
        'Bob cannot delete the workspace', api(bob_context, 'DELETE', f'/api/workspaces/{workspace_id}/').status == 403
    )

    def bob_settings_are_read_only():
        bob.goto(f'/projects/{project_id}/settings')
        expect(bob.get_by_test_id('workspace-select')).to_contain_text('Metabolomics')
        expect(bob.get_by_test_id('workspace-select')).to_be_disabled()

    step('Bob sees the workspace selector disabled', bob_settings_are_read_only)

    # --- moving the project out and back ------------------------------------------------------------
    def detach_from_settings():
        alice.goto(f'/projects/{project_id}/settings')
        expect(alice.get_by_test_id('workspace-select')).to_contain_text('Metabolomics')
        choose(alice, 'workspace-select', 'none')
        expect(alice.get_by_test_id('workspace-select')).to_contain_text('No workspace')

    step('Alice takes the project out of the workspace from its settings', detach_from_settings)
    check(
        'the project is in no workspace',
        api(alice_context, 'GET', f'/api/projects/{project_id}/workspace/').json()['workspace'] is None,
    )
    check('Bob lost the project', api(bob_context, 'GET', f'/api/projects/{project_id}/').status in (403, 404))

    def attach_from_settings():
        choose(alice, 'workspace-select', str(workspace_id))
        shoot(alice, '6b-confirmation')
        alice.get_by_role('button', name='Change', exact=True).click()
        expect(alice.get_by_test_id('workspace-select')).to_contain_text('Metabolomics')

    step('Alice puts it back, after a confirmation', attach_from_settings)
    check('Bob reads the project again', api(bob_context, 'GET', f'/api/projects/{project_id}/').status == 200)

    # --- the administrator, then deletion -----------------------------------------------------------
    admin_workspaces = api(admin_context, 'GET', '/api/workspaces/').json()
    check(
        'admin sees the workspace and may manage it',
        [w['can_manage'] for w in admin_workspaces] == [True],
        admin_workspaces,
    )

    def delete_workspace():
        alice.goto(f'/projects?workspace={workspace_id}')
        alice.get_by_test_id(f'workspace-settings-button-{workspace_id}').click()
        alice.get_by_test_id('workspace-delete-button').click()
        confirmation = alice.locator('[class*="modal-ls"]').filter(has_text='Its projects are kept')
        confirmation.get_by_role('button', name='Delete', exact=True).first.click()
        expect(alice.get_by_test_id(f'workspace-item-{workspace_id}')).to_have_count(0)
        expect(alice.get_by_text('Lipids').first).to_be_visible()

    step('Alice deletes the workspace; the list falls back to all projects', delete_workspace)
    check('the project survived', api(alice_context, 'GET', f'/api/projects/{project_id}/').status == 200)
    check(
        'Bob lost the project for good', api(bob_context, 'GET', f'/api/projects/{project_id}/').status in (403, 404)
    )
    shoot(alice, '7-apres-suppression')
    browser.close()

passed = sum(1 for _, ok in results if ok)
print(f'\n{passed}/{len(results)} checks passed')
sys.exit(0 if passed == len(results) else 1)
