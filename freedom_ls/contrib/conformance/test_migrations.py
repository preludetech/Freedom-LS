"""Migration-state probe.

Diffs the project's models against its migration files entirely from disk: the
loader is built with no database connection, so the probe never opens a socket
and needs no test-database records or `django_db` marker. A downstream missing
migration surfaces as a named app in the detected changes.
"""

from __future__ import annotations

from django.apps import apps
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

__all__ = ["test_migration_state_consistent"]


def test_migration_state_consistent() -> None:
    loader = MigrationLoader(None, ignore_no_migrations=True)
    autodetector = MigrationAutodetector(
        loader.project_state(),
        ProjectState.from_apps(apps),
    )
    changes = autodetector.changes(graph=loader.graph)
    assert not changes, f"Models have drifted from migrations: {sorted(changes)}"
