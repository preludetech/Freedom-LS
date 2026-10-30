"""`record_run`: the status and timestamps every recorded run passes through."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site

from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.panel_framework.run_records import record_run

from .helpers import make_staff_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def run(mock_site_context: Site) -> BulkActionRun:
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            requested_by=make_staff_user(),
            action_path="panel_framework.tests.stub_panels.StubRecordedBulkAction",
            table_key="stubs",
            action_name="stub_recorded",
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


def test_extra_fields_the_body_sets_are_saved_with_the_outcome(run: BulkActionRun):
    with record_run(run, extra_fields=("result",)):
        run.result, run.status = {"counts": []}, RunStatus.DONE

    run.refresh_from_db()
    assert run.result == {"counts": []}


def test_a_field_not_named_as_extra_is_not_saved(run: BulkActionRun):
    with record_run(run):
        run.result, run.status = {"counts": []}, RunStatus.DONE

    run.refresh_from_db()
    assert run.result is None
