"""Migration-state probe.

Diffs the project's models against its migration files entirely from disk: the
loader is built with no database connection, so the probe never opens a socket
and needs no test-database records or `django_db` marker. A downstream missing
migration surfaces as a named app in the detected changes.

Models defined under a `tests` package are left out of the comparison. A
test-only stub model is registered under its app's label but has its table
built by a session fixture and never a migration, so it is a fixture, not
drift.
"""

from __future__ import annotations

from django.apps import apps
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ModelState, ProjectState

__all__ = ["test_migration_state_consistent"]


def _shipped_models_state() -> ProjectState:
    """`ProjectState.from_apps` minus the models a `tests` package defines."""
    models: dict[tuple[str, str], ModelState] = {}
    for model in apps.get_models(include_swapped=True):
        if "tests" in model.__module__.split("."):
            continue
        state = ModelState.from_model(model)
        models[(state.app_label, state.name_lower)] = state
    return ProjectState(models)


def test_migration_state_consistent() -> None:
    loader = MigrationLoader(None, ignore_no_migrations=True)
    autodetector = MigrationAutodetector(
        loader.project_state(),
        _shipped_models_state(),
    )
    changes = autodetector.changes(graph=loader.graph)
    assert not changes, f"Models have drifted from migrations: {sorted(changes)}"
