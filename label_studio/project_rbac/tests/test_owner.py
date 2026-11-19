"""Security tests for project ownership (ADR 0002): creation by members, owner role, deletion, invitation."""

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.skip(reason='skeleton: lot 1 not implemented yet')]


def test_member_creates_project_and_becomes_its_manager():
    raise NotImplementedError
