"""`claim_run` and `record_run`: the status and timestamps every recorded run
passes through."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.db.models import QuerySet

from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.panel_framework.run_records import claim_run, record_run

from .helpers import make_staff_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def records(mock_site_context: Site) -> QuerySet[BulkActionRun]:
    created = BulkActionRun.objects.create(
        requested_by=make_staff_user(),
        action_path="panel_framework.tests.stub_panels.StubRecordedBulkAction",
        table_key="stubs",
        action_name="stub_recorded",
    )
    return BulkActionRun._base_manager.filter(pk=created.pk)


@pytest.fixture
def run(records: QuerySet[BulkActionRun]) -> BulkActionRun:
    return cast(BulkActionRun, claim_run(records))


def test_claiming_marks_the_record_running(records: QuerySet[BulkActionRun]):
    run = claim_run(records)

    in_flight = records.get()
    assert run is not None
    assert (in_flight.status, in_flight.started_at is not None) == (
        RunStatus.RUNNING,
        True,
    )


@pytest.mark.parametrize(
    "status", [RunStatus.RUNNING, RunStatus.DONE, RunStatus.FAILED]
)
def test_a_record_that_is_not_queued_cannot_be_claimed(
    records: QuerySet[BulkActionRun], status: RunStatus
):
    records.update(status=status, error_message="as it was")

    assert claim_run(records) is None
    assert (records.get().status, records.get().error_message) == (status, "as it was")


def test_an_unclaimed_record_is_refused(records: QuerySet[BulkActionRun]):
    with (
        pytest.raises(ValueError, match="claim_run"),
        record_run(records.get(), records),
    ):
        pass


def test_a_body_that_marks_the_run_done_leaves_it_done(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    with record_run(run, records):
        run.status = RunStatus.DONE

    run.refresh_from_db()
    assert run.status == RunStatus.DONE


def test_finished_at_is_stamped_when_the_body_succeeds(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    with record_run(run, records):
        run.status = RunStatus.DONE

    run.refresh_from_db()
    assert run.finished_at is not None


def test_an_exception_fails_the_run_and_still_propagates(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    with pytest.raises(RuntimeError, match="boom"), record_run(run, records):
        raise RuntimeError("boom")

    run.refresh_from_db()
    assert (run.status, run.error_message) == (RunStatus.FAILED, "Unexpected error.")


def test_finished_at_is_stamped_when_the_body_raises(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    with pytest.raises(RuntimeError), record_run(run, records):
        raise RuntimeError("boom")

    run.refresh_from_db()
    assert run.finished_at is not None


def test_a_body_that_fails_the_run_keeps_its_own_message(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    with record_run(run, records):
        run.status, run.error_message = RunStatus.FAILED, "Nothing to do."

    run.refresh_from_db()
    assert (run.status, run.error_message) == (RunStatus.FAILED, "Nothing to do.")


def test_extra_fields_the_body_sets_are_saved_with_the_outcome(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    with record_run(run, records, extra_fields=("result",)):
        run.result, run.status = {"counts": []}, RunStatus.DONE

    run.refresh_from_db()
    assert run.result == {"counts": []}


def test_a_field_not_named_as_extra_is_not_saved(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    with record_run(run, records):
        run.result, run.status = {"counts": []}, RunStatus.DONE

    run.refresh_from_db()
    assert run.result is None


def test_a_record_a_sweep_closed_mid_run_keeps_the_sweeps_verdict(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    with record_run(run, records, extra_fields=("result",)):
        records.update(status=RunStatus.FAILED, error_message="swept")
        run.result, run.status = {"counts": []}, RunStatus.DONE

    run.refresh_from_db()
    assert (run.status, run.error_message, run.result) == (
        RunStatus.FAILED,
        "swept",
        None,
    )


def test_on_closed_is_told_once_this_process_closes_the_record(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    closed: list[str] = []
    with record_run(run, records, on_closed=lambda r: closed.append(r.status)):
        run.status = RunStatus.DONE

    assert closed == [RunStatus.DONE]


def test_on_closed_is_not_told_when_a_sweep_closed_it_first(
    run: BulkActionRun, records: QuerySet[BulkActionRun]
):
    closed: list[str] = []
    with record_run(run, records, on_closed=lambda r: closed.append(r.status)):
        records.update(status=RunStatus.FAILED, error_message="swept")
        run.status = RunStatus.DONE

    assert closed == []
