"""The data migration that points stored bulk runs at the cohort bulk action module."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils.module_loading import import_string

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.panel_framework.bulk_actions import RecordedBulkAction

APP = "freedom_ls_educator_interface"
RUNS = "freedom_ls_panel_framework"
BEFORE = [(APP, "0002_move_learner_bulk_runs")]
AFTER = [(APP, "0003_move_cohort_bulk_runs")]
OLD = "freedom_ls.educator_interface.actions."
NEW = "freedom_ls.educator_interface.panels.cohort.bulk_actions."
LEARNER_NEW = "freedom_ls.educator_interface.panels.learner.bulk_actions."

# (class name, action_name) for every cohort bulk action a run can be stored under.
COHORT_ACTIONS = [
    ("RegisterCohortForCourseBulkAction", "register"),
    ("DeactivateCohortRegistrationBulkAction", "deactivate_cohort_registration"),
    ("DeactivateCohortsBulkAction", "deactivate"),
    ("ReactivateCohortsBulkAction", "reactivate"),
]


@pytest.fixture
def migrated_back_to_the_leaf() -> Iterator[None]:
    """Every test here migrates down to 0002 and up again; leave the schema at
    the leaf so later tests see the full schema."""
    yield
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())


def _historical_model() -> type:
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    return executor.loader.project_state([(RUNS, "0001_initial")]).apps.get_model(
        RUNS, "BulkActionRun"
    )


def _migrate(target: list[tuple[str, str]]) -> type:
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(target)
    return executor.loader.project_state(target).apps.get_model(RUNS, "BulkActionRun")


def _make_run(model: type, site: Site, user: User, path: str, name: str) -> object:
    return model.objects.create(
        site_id=site.pk,
        requested_by_id=user.pk,
        action_path=path,
        table_key="cohorts",
        action_name=name,
        keys=[],
    ).pk


def _stored(model: type, pk: object) -> tuple[str, str]:
    run = model.objects.get(pk=pk)
    return run.action_path, run.action_name


# transaction=True: the tests migrate backwards and forwards.
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("name, action_name", COHORT_ACTIONS)
def test_cohort_run_points_at_the_cohort_bulk_action_module(
    name: str,
    action_name: str,
    mock_site_context: object,
    migrated_back_to_the_leaf: None,
) -> None:
    user = UserFactory()
    site = Site.objects.get_current()
    Historical = _historical_model()
    run = _make_run(Historical, site, user, f"{OLD}{name}", action_name)

    Current = _migrate(AFTER)

    assert _stored(Current, run) == (f"{NEW}{name}", action_name)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("name, action_name", COHORT_ACTIONS)
def test_migrating_back_restores_a_cohort_run_to_its_old_path(
    name: str,
    action_name: str,
    mock_site_context: object,
    migrated_back_to_the_leaf: None,
) -> None:
    user = UserFactory()
    site = Site.objects.get_current()
    Historical = _historical_model()
    run = _make_run(Historical, site, user, f"{OLD}{name}", action_name)
    _migrate(AFTER)

    Restored = _migrate(BEFORE)

    assert _stored(Restored, run) == (f"{OLD}{name}", action_name)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "path, action_name",
    [
        (f"{LEARNER_NEW}DeactivateLearnersBulkAction", "deactivate"),
        (f"{OLD}NoSuchBulkAction", "unknown"),
    ],
)
def test_run_of_another_action_is_left_alone(
    path: str, action_name: str, mock_site_context: object, migrated_back_to_the_leaf: None
) -> None:
    user = UserFactory()
    site = Site.objects.get_current()
    Historical = _historical_model()
    run = _make_run(Historical, site, user, path, action_name)

    Current = _migrate(AFTER)

    assert _stored(Current, run) == (path, action_name)


@pytest.mark.django_db(transaction=True)
def test_run_already_on_a_new_path_is_left_alone(
    mock_site_context: object, migrated_back_to_the_leaf: None
) -> None:
    user = UserFactory()
    site = Site.objects.get_current()
    Historical = _historical_model()
    path = f"{NEW}DeactivateCohortsBulkAction"
    run = _make_run(Historical, site, user, path, "deactivate")

    Current = _migrate(AFTER)

    assert _stored(Current, run) == (path, "deactivate")


@pytest.mark.parametrize("name", [name for name, _ in COHORT_ACTIONS])
def test_each_new_path_imports_a_recorded_bulk_action(name: str) -> None:
    assert issubclass(import_string(f"{NEW}{name}"), RecordedBulkAction)
