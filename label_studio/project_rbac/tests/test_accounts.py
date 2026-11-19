"""Security tests for account administration (ADR 0003)."""

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.skip(reason='skeleton: lot 3 not implemented yet')]


def test_only_administrators_manage_accounts():
    raise NotImplementedError
