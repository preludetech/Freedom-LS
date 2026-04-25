"""Shared helper for tests that verify DB-level grants.

``require_nonsuperuser`` inspects ``pg_roles.rolsuper`` for ``current_user``
on the given connection and fails the test if the role is a Postgres
superuser, because superusers bypass ``REVOKE``/``GRANT`` and would make
grant-verification tests pass for the wrong reason.

Pytest runs as the non-superuser ``fls_app`` role by default (see
``[tool.pytest.ini_options].env`` in ``pyproject.toml``); this helper is
the tripwire that catches any configuration that regresses that.
"""

from __future__ import annotations

import pytest


def require_nonsuperuser(connection, what: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        row = cursor.fetchone()
    if row and row[0]:
        pytest.fail(
            f"{what} is a Postgres superuser; grants are bypassed. "
            "Run this test against a non-superuser role."
        )
