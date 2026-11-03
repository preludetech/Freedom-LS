"""The data migration that points stored bulk runs at the renamed action classes."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from freedom_ls.accounts.factories import UserFactory

APP = "freedom_ls_educator_interface"
RUNS = "freedom_ls_panel_framework"
ACTIONS = "freedom_ls.educator_interface.actions."


# transaction=True: the test migrates backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_runs_recorded_under_the_old_class_names_point_at_the_new_ones(
    mock_site_context: object,
) -> None:
    user = UserFactory()
    site = Site.objects.get_current()

    executor = MigrationExecutor(connection)
    leaf = executor.loader.graph.leaf_nodes()
    executor.migrate([(APP, None)])
    old_apps = executor.loader.project_state([(RUNS, "0001_initial")]).apps
    Historical = old_apps.get_model(RUNS, "BulkActionRun")

    def make(action_path: str, action_name: str) -> object:
        return Historical.objects.create(
            site_id=site.pk,
            requested_by_id=user.pk,
            action_path=action_path,
            table_key="learners",
            action_name=action_name,
            keys=[],
        ).pk

    learner_run = make(f"{ACTIONS}UnregisterFromCourseBulkAction", "unregister_from_course")
    cohort_run = make(f"{ACTIONS}UnregisterCohortFromCourseBulkAction", "unregister")
    untouched = make(f"{ACTIONS}DeactivateLearnersBulkAction", "deactivate")

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(leaf)
    Current = executor.loader.project_state(leaf).apps.get_model(RUNS, "BulkActionRun")

    def stored(pk: object) -> tuple[str, str]:
        run = Current.objects.get(pk=pk)
        return run.action_path, run.action_name

    assert stored(learner_run) == (
        f"{ACTIONS}DeactivateRegistrationBulkAction",
        "deactivate_registration",
    )
    assert stored(cohort_run) == (
        f"{ACTIONS}DeactivateCohortRegistrationBulkAction",
        "deactivate_cohort_registration",
    )
    assert stored(untouched) == (f"{ACTIONS}DeactivateLearnersBulkAction", "deactivate")
