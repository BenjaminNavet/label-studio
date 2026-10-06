"""Create organization members with random passwords; run inside the container through ``manage.py shell``.

Reads ``RBAC_USERS`` (comma-separated emails) and prints ``email<TAB>password`` for each account created.
Existing accounts are left untouched.
"""

import os
import secrets

from organizations.models import Organization
from users.models import User

organization = Organization.objects.order_by('id').first()
for email in filter(None, (part.strip() for part in os.environ['RBAC_USERS'].split(','))):
    if User.objects.filter(email=email).exists():
        print(f'{email}\t(already exists)')
        continue
    password = secrets.token_urlsafe(12)
    user = User.objects.create_user(email=email, password=password, username=email.split('@')[0])
    organization.add_user(user)
    user.active_organization = organization
    user.save(update_fields=['active_organization'])
    print(f'{email}\t{password}')
