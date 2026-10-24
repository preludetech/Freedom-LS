"""`record_run`: the status and timestamps every recorded run passes through."""

from __future__ import annotations

from typing import cast

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.models import BulkActionRun, RunStatus
from freedom_ls.learner_management.run_records import record_run
from freedom_ls.organisations.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def run(mock_site_context) -> BulkActionRun:
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            organisation=OrganisationFactory(),
            requested_by=UserFactory(),
            table_key="learners",
            action_name="deactivate",
        ),
    )


def test_a_body_that_marks_the_run_done_leaves_it_done(run: BulkActionRun):
    with record_run(run):
        run.status = RunStatus.DONE

    run.refresh_from_db()
    assert run.status == RunStatus.DONE


def test_the_run_is_running_while_the_body_executes(run: BulkActionRun):
    with record_run(run):
        in_flight = BulkActionRun.objects.get(pk=run.pk)

    assert (in_flight.status, in_flight.started_at is not None) == (
        RunStatus.RUNNING,
        True,
    )


def test_finished_at_is_stamped_when_the_body_succeeds(run: BulkActionRun):
    with record_run(run):
        run.status = RunStatus.DONE

    run.refresh_from_db()
    assert run.finished_at is not None


def test_an_exception_fails_the_run_and_still_propagates(run: BulkActionRun):
    with pytest.raises(RuntimeError, match="boom"), record_run(run):
        raise RuntimeError("boom")

    run.refresh_from_db()
    assert (run.status, run.error_message) == (RunStatus.FAILED, "Unexpected error.")


def test_finished_at_is_stamped_when_the_body_raises(run: BulkActionRun):
    with pytest.raises(RuntimeError), record_run(run):
        raise RuntimeError("boom")

    run.refresh_from_db()
    assert run.finished_at is not None


def test_a_body_that_fails_the_run_keeps_its_own_message(run: BulkActionRun):
    with record_run(run):
        run.status, run.error_message = RunStatus.FAILED, "Nothing to do."

    run.refresh_from_db()
    assert (run.status, run.error_message) == (RunStatus.FAILED, "Nothing to do.")
