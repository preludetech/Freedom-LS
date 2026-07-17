"""Migration-state probe.

Diffs models against migration files. The check may open a database
connection to read the applied-migrations history, but Django swallows the
resulting OperationalError when the database is unreachable, so this stays
green with or without a live database. No transactional test-DB setup or
records are required, so the probe only unblocks pytest-django's database
guard rather than requesting the `django_db` marker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.management import call_command

if TYPE_CHECKING:
    from pytest_django.fixtures import DjangoDbBlocker

__all__ = ["test_migration_state_consistent"]


def test_migration_state_consistent(django_db_blocker: DjangoDbBlocker) -> None:
    with django_db_blocker.unblock():
        call_command("makemigrations", check=True, dry_run=True, verbosity=0)
