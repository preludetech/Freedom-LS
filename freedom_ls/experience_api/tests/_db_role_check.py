"""Shared helper for tests that verify DB-level grants.

``require_nonsuperuser_or_skip`` inspects ``pg_roles.rolsuper`` for
``current_user`` on the given connection. If the role is a superuser:

- When ``FLS_REQUIRE_NONSUPERUSER_DB=1`` (set in CI): ``pytest.fail``.
- Otherwise (local dev): ``pytest.skip``.

This keeps local DX unchanged while ensuring CI cannot silently pass
grant-enforcement tests by running as a Postgres superuser.
"""

from __future__ import annotations

import os

import pytest


def require_nonsuperuser_or_skip(connection, what: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        row = cursor.fetchone()
    if not (row and row[0]):
        return
    msg = (
        f"{what} is a Postgres superuser; grants are bypassed. "
        "Run this test against a non-superuser role."
    )
    if os.environ.get("FLS_REQUIRE_NONSUPERUSER_DB"):
        pytest.fail(msg)
    pytest.skip(msg)
