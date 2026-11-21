"""The data migration that points stored bulk runs at the learner bulk action module."""

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
BEFORE = [(APP, "0001_rename_unregister_bulk_runs")]
AFTER = [(APP, "0002_move_learner_bulk_runs")]
OLD = "freedom_ls.educator_interface.actions."
NEW = "freedom_ls.educator_interface.panels.learner.bulk_actions."

# (class name, action_name) for every learner bulk action a run can be stored under.
LEARNER_ACTIONS = [
    ("AddToCohortBulkAction", "add_to_cohort"),
    ("RemoveFromCohortBulkAction", "remove_from_cohort"),
    ("DeactivateLearnersBulkAction", "deactivate"),
    ("ReactivateLearnersBulkAction", "reactivate"),
    ("RegisterForCourseBulkAction", "register_for_course"),
    ("DeactivateRegistrationBulkAction", "deactivate_registration"),
    ("ResendSetupEmailBulkAction", "resend_setup_email"),
]


@pytest.fixture
def migrated_back_to_the_leaf() -> Iterator[None]:
    """Every test here migrates down to 0001 and up again; leave the schema at
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
        table_key="learners",
        action_name=name,
        keys=[],
    ).pk


def _stored(model: type, pk: object) -> tuple[str, str]:
    run = model.objects.get(pk=pk)
    return run.action_path, run.action_name


# transaction=True: the tests migrate backwards and forwards.
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "old_path, new_path",
    [
        ("freedom_ls.educator_interface.actions.AddToCohortBulkAction", "freedom_ls.educator_interface.panels.learner.bulk_actions.AddToCohortBulkAction"),
        ("freedom_ls.educator_interface.actions.RemoveFromCohortBulkAction", "freedom_ls.educator_interface.panels.learner.bulk_actions.RemoveFromCohortBulkAction"),
        ("freedom_ls.educator_interface.actions.DeactivateLearnersBulkAction", "freedom_ls.educator_interface.panels.learner.bulk_actions.DeactivateLearnersBulkAction"),
        ("freedom_ls.educator_interface.actions.ReactivateLearnersBulkAction", "freedom_ls.educator_interface.panels.learner.bulk_actions.ReactivateLearnersBulkAction"),
        ("freedom_ls.educator_interface.actions.RegisterForCourseBulkAction", "freedom_ls.educator_interface.panels.learner.bulk_actions.RegisterForCourseBulkAction"),
        ("freedom_ls.educator_interface.actions.DeactivateRegistrationBulkAction", "freedom_ls.educator_interface.panels.learner.bulk_actions.DeactivateRegistrationBulkAction"),
        ("freedom_ls.educator_interface.actions.ResendSetupEmailBulkAction", "freedom_ls.educator_interface.panels.learner.bulk_actions.ResendSetupEmailBulkAction"),
    ],
)
def test_learner_run_points_at_the_learner_bulk_action_module(
    old_path: str,
    new_path: str,
    mock_site_context: object,
    migrated_back_to_the_leaf: None,
) -> None:
    user = UserFactory()
    site = Site.objects.get_current()
    Historical = _historical_model()
    run = _make_run(Historical, site, user, old_path, "any_action")

    Current = _migrate(AFTER)

    assert _stored(Current, run)[0] == new_path


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("action_name", [action_name for _, action_name in LEARNER_ACTIONS])
def test_learner_run_keeps_its_action_name_when_moved(
    action_name: str, mock_site_context: object, migrated_back_to_the_leaf: None
) -> None:
    user = UserFactory()
    site = Site.objects.get_current()
    Historical = _historical_model()
    run = _make_run(
        Historical,
        site,
        user,
        "freedom_ls.educator_interface.actions.AddToCohortBulkAction",
        action_name,
    )

    Current = _migrate(AFTER)

    assert _stored(Current, run)[1] == action_name


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "new_path, old_path",
    [
        ("freedom_ls.educator_interface.panels.learner.bulk_actions.AddToCohortBulkAction", "freedom_ls.educator_interface.actions.AddToCohortBulkAction"),
        ("freedom_ls.educator_interface.panels.learner.bulk_actions.RemoveFromCohortBulkAction", "freedom_ls.educator_interface.actions.RemoveFromCohortBulkAction"),
        ("freedom_ls.educator_interface.panels.learner.bulk_actions.DeactivateLearnersBulkAction", "freedom_ls.educator_interface.actions.DeactivateLearnersBulkAction"),
        ("freedom_ls.educator_interface.panels.learner.bulk_actions.ReactivateLearnersBulkAction", "freedom_ls.educator_interface.actions.ReactivateLearnersBulkAction"),
        ("freedom_ls.educator_interface.panels.learner.bulk_actions.RegisterForCourseBulkAction", "freedom_ls.educator_interface.actions.RegisterForCourseBulkAction"),
        ("freedom_ls.educator_interface.panels.learner.bulk_actions.DeactivateRegistrationBulkAction", "freedom_ls.educator_interface.actions.DeactivateRegistrationBulkAction"),
        ("freedom_ls.educator_interface.panels.learner.bulk_actions.ResendSetupEmailBulkAction", "freedom_ls.educator_interface.actions.ResendSetupEmailBulkAction"),
    ],
)
def test_migrating_back_restores_a_learner_run_to_its_old_path(
    new_path: str,
    old_path: str,
    mock_site_context: object,
    migrated_back_to_the_leaf: None,
) -> None:
    user = UserFactory()
    site = Site.objects.get_current()
    Historical = _historical_model()
    run = _make_run(Historical, site, user, old_path, "any_action")
    _migrate(AFTER)

    Restored = _migrate(BEFORE)

    assert _stored(Restored, run)[0] == old_path


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "path, action_name",
    [
        ("freedom_ls.educator_interface.actions.DeactivateCohortsBulkAction", "deactivate"),
        ("freedom_ls.educator_interface.actions.NoSuchBulkAction", "unknown"),
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
    run = _make_run(
        Historical,
        site,
        user,
        "freedom_ls.educator_interface.panels.learner.bulk_actions.AddToCohortBulkAction",
        "add_to_cohort",
    )

    Current = _migrate(AFTER)

    assert _stored(Current, run) == (
        "freedom_ls.educator_interface.panels.learner.bulk_actions.AddToCohortBulkAction",
        "add_to_cohort",
    )


@pytest.mark.parametrize("name", [name for name, _ in LEARNER_ACTIONS])
def test_each_new_path_imports_a_recorded_bulk_action(name: str) -> None:
    assert issubclass(import_string(f"{NEW}{name}"), RecordedBulkAction)
