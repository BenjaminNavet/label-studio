"""Create one project per task group and assign roles, through the public API (standard library only).

Example::

    python3 seed_projects.py --url http://localhost:8080 --token "$LABEL_STUDIO_USER_TOKEN" \\
        --label-config label_config.xml --tasks tasks.json --group-by batch --title-prefix "chem-lab" \\
        --role audit:annotator1@local.test:annotator --role validation:annotator2@local.test:annotator \\
        --role '*:manager@local.test:manager'

``--role GROUP:EMAIL:ROLE`` grants ROLE on the project of GROUP (``*`` = every project).
"""

import argparse
import json
import urllib.error
import urllib.request
from collections import defaultdict


def call(base_url, token, method, path, payload=None):
    """Send one JSON request and return the decoded response."""
    request = urllib.request.Request(
        f'{base_url}{path}',
        method=method,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Authorization': f'Token {token}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise SystemExit(f'{method} {path} -> {error.code}: {error.read().decode()[:300]}') from error
    return json.loads(body) if body else None


def main():
    """Create the projects, import their tasks and grant the roles."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('--label-config', required=True)
    parser.add_argument('--tasks', required=True)
    parser.add_argument('--group-by', required=True, help='task data field that splits tasks into projects')
    parser.add_argument('--title-prefix', default='')
    parser.add_argument('--role', action='append', default=[], help='GROUP:EMAIL:ROLE')
    args = parser.parse_args()

    with open(args.label_config, encoding='utf-8') as handle:
        label_config = handle.read()
    with open(args.tasks, encoding='utf-8') as handle:
        tasks = json.load(handle)
    tasks_by_group = defaultdict(list)
    for task in tasks:
        tasks_by_group[task['data'][args.group_by]].append(task)

    members = call(args.url, args.token, 'GET', '/api/users/')
    user_id_by_email = {member['email']: member['id'] for member in members}

    project_id_by_group = {}
    for group, group_tasks in sorted(tasks_by_group.items()):
        title = f'{args.title_prefix} · {group}' if args.title_prefix else group
        project = call(args.url, args.token, 'POST', '/api/projects/', {'title': title, 'label_config': label_config})
        call(args.url, args.token, 'POST', f'/api/projects/{project["id"]}/import', group_tasks)
        project_id_by_group[group] = project['id']
        print(f'project {project["id"]} "{title}": {len(group_tasks)} tasks')

    for spec in args.role:
        group, email, role = spec.split(':')
        groups = project_id_by_group if group == '*' else [group]
        for target in groups:
            project_id = project_id_by_group[target]
            call(args.url, args.token, 'POST', f'/api/projects/{project_id}/roles/', {'user': user_id_by_email[email], 'role': role})
            print(f'{email}: {role} on project {project_id} ({target})')


if __name__ == '__main__':
    main()
