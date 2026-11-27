"""The migration that drops the table, migration records and content types left by the
`freedom_ls_panel_framework` app label."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest

from django.apps import apps
from django.apps.registry import Apps
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.models.deletion import ProtectedError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.educator_interface.tests.migrations import legacy_rows

APP = "freedom_ls_educator_interface"
BEFORE = [(APP, "0003_move_cohort_bulk_runs")]
AFTER = [(APP, "0004_drop_legacy_panel_framework")]
LEGACY_LABEL = "freedom_ls_panel_framework"
LEGACY_TABLE = "freedom_ls_panel_framework_bulkactionrun"
CURRENT_TABLE = "panel_framework_bulkactionrun"

migration_module = importlib.import_module(
    "freedom_ls.educator_interface.migrations.0004_drop_legacy_panel_framework"
)
# The educator interface's own earlier migrations are ancestors by design.
OTHER_APP_DEPENDENCIES = [
    dependency
    for dependency in migration_module.Migration.dependencies
    if dependency[0] != APP
]


def _table_names() -> list[str]:
    return connection.introspection.table_names()


def _migrate(target: list[tuple[str, str]]) -> None:
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(target)


@pytest.fixture
def at_0003() -> Iterator[None]:
    """Migrate back to 0003 and, at teardown, forward to the leaves, so later tests
    see the full schema."""
    _migrate(BEFORE)
    yield
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.fixture
def legacy_state(at_0003: None, mock_site_context: object) -> Iterator[ContentType]:
    """The legacy table, two of its migration records, and a content type with a
    permission and an admin log entry pointing at it."""

    class LegacyBulkActionRun(models.Model):
        class Meta:
            apps = Apps()
            app_label = "legacy_panel_framework_fixture"
            db_table = LEGACY_TABLE

    with connection.schema_editor() as editor:
        editor.create_model(LegacyBulkActionRun)
    recorder = MigrationRecorder(connection)
    recorder.record_applied(LEGACY_LABEL, "0001_initial")
    recorder.record_applied(LEGACY_LABEL, "0002_bulkactionrun_scope")
    ct = ContentType.objects.create(app_label=LEGACY_LABEL, model="bulkactionrun")
    legacy_rows.permission(ct)
    legacy_rows.log_entry(ct)
    yield ct
    if LEGACY_TABLE in _table_names():
        with connection.schema_editor() as editor:
            editor.delete_model(LegacyBulkActionRun)
    # The audit log refuses `delete()`, so a protecting row goes through the base queryset.
    models.QuerySet.delete(
        AuditLogEntry._base_manager.filter(
            target_content_type__app_label=LEGACY_LABEL
        )
    )
    recorder.migration_qs.filter(app=LEGACY_LABEL).delete()
    ContentType.objects.filter(app_label=LEGACY_LABEL).delete()


@pytest.mark.django_db(transaction=True)
def test_legacy_table_is_dropped(legacy_state: ContentType) -> None:
    _migrate(AFTER)

    assert LEGACY_TABLE not in _table_names()


@pytest.mark.django_db(transaction=True)
def test_legacy_migration_records_are_removed(legacy_state: ContentType) -> None:
    _migrate(AFTER)

    assert not MigrationRecorder(connection).migration_qs.filter(
        app=LEGACY_LABEL
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_legacy_content_type_is_removed(legacy_state: ContentType) -> None:
    _migrate(AFTER)

    assert not ContentType.objects.filter(app_label=LEGACY_LABEL).exists()


@pytest.mark.django_db(transaction=True)
def test_permission_on_the_legacy_content_type_is_removed(
    legacy_state: ContentType,
) -> None:
    _migrate(AFTER)

    assert not Permission.objects.filter(codename="legacy_perm").exists()


@pytest.mark.django_db(transaction=True)
def test_admin_log_entry_on_the_legacy_content_type_keeps_its_row_without_a_type(
    legacy_state: ContentType,
) -> None:
    """`LogEntry.content_type` is `SET_NULL`: the entry stays, its type goes."""
    _migrate(AFTER)

    assert LogEntry.objects.get(object_repr="legacy").content_type is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("label", list(legacy_rows.CASCADING))
def test_row_pointing_at_the_legacy_content_type_is_removed(
    label: str, legacy_state: ContentType, mock_site_context: object
) -> None:
    row = legacy_rows.CASCADING[label](legacy_state)

    _migrate(AFTER)

    assert not row.exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("label", list(legacy_rows.PROTECTING))
def test_row_protecting_the_legacy_content_type_makes_the_migration_raise(
    label: str, legacy_state: ContentType, mock_site_context: object
) -> None:
    legacy_rows.PROTECTING[label](legacy_state)

    with pytest.raises(ProtectedError):
        _migrate(AFTER)


@pytest.mark.django_db(transaction=True)
def test_current_panel_framework_table_and_its_rows_are_untouched(
    legacy_state: ContentType, mock_site_context: object
) -> None:
    from panel_framework.models import BulkActionRun

    # The installed package's model does not fill in the site on save.
    run = BulkActionRun.objects.create(
        site=Site.objects.get_current(),
        requested_by=UserFactory(),
        action_path="x.Y",
        table_key="t",
        action_name="a",
    )

    _migrate(AFTER)

    assert CURRENT_TABLE in _table_names()
    assert BulkActionRun.objects.filter(pk=run.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_running_the_migration_function_again_changes_nothing(
    legacy_state: ContentType,
) -> None:
    _migrate(AFTER)
    tables = _table_names()
    content_types = ContentType.objects.count()

    with connection.schema_editor() as editor:
        migration_module.drop_legacy_panel_framework(apps, editor)

    assert (_table_names(), ContentType.objects.count()) == (tables, content_types)


@pytest.mark.django_db(transaction=True)
def test_migration_with_nothing_arranged_removes_nothing(at_0003: None) -> None:
    tables = _table_names()
    content_types = ContentType.objects.count()

    _migrate(AFTER)

    assert (_table_names(), ContentType.objects.count()) == (tables, content_types)


@pytest.mark.django_db
@pytest.mark.parametrize("dependency", OTHER_APP_DEPENDENCIES)
def test_dependency_has_no_ancestor_in_the_educator_interface(
    dependency: tuple[str, str],
) -> None:
    graph = MigrationLoader(connection).graph

    ancestor_apps = {app for app, _ in graph.forwards_plan(dependency)}

    assert APP not in ancestor_apps
