"""`run_bulk_action`: a recorded bulk action run from nothing but its id, and
the hook a background run reaches when it finishes."""

from __future__ import annotations

import inspect
from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.http import Http404

from freedom_ls.panel_framework.bulk_actions import BulkCount, BulkResult
from freedom_ls.panel_framework.bulk_runs import (
    ACTION_UNAVAILABLE,
    NOT_FOUND,
    action_for,
    report_finished,
    run_bulk_action,
    run_summary,
)
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.panel_framework.tasks import _run_bulk_action_task
from freedom_ls.tests.site_context import drop_ambient_request

from .helpers import make_staff_user, make_stub
from .stub_models import StubModel
from .stub_panels import StubRecordedBulkAction

pytestmark = pytest.mark.django_db

GONE = "999999"
ACTION_PATH = f"{StubRecordedBulkAction.__module__}.StubRecordedBulkAction"


@pytest.fixture(autouse=True)
def _clear_hook_log():
    StubRecordedBulkAction.finished.clear()
    yield
    StubRecordedBulkAction.finished.clear()


def _run_over(stub: StubModel, *others: str, **fields: object) -> BulkActionRun:
    fields.setdefault("action_path", ACTION_PATH)
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            requested_by=make_staff_user(),
            table_key="stubs",
            action_name="stub_recorded",
            keys=[str(stub.pk), *others],
            **fields,
        ),
    )


def test_it_resolves_the_run_with_no_ambient_site(mock_site_context: Site):
    stub = make_stub()
    run = _run_over(stub)
    drop_ambient_request()

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    stub.refresh_from_db()
    assert (result.changed, stub.is_active) == (1, False)


def test_it_stores_the_result_json_and_marks_the_run_done(mock_site_context: Site):
    run = _run_over(make_stub())

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    run = BulkActionRun._base_manager.get(pk=run.pk)
    assert run.status == RunStatus.DONE
    assert run.result == result.to_json()
    assert run.finished_at is not None


def test_a_stale_key_is_reported_as_not_found(mock_site_context: Site):
    run = _run_over(make_stub(), GONE)

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    assert BulkCount("skipped", NOT_FOUND, 1) in result.counts
    assert [(entry.key, entry.reason) for entry in result.entries] == [
        (GONE, NOT_FOUND)
    ]
    assert StubRecordedBulkAction().result_line(result.counts[-1]) == "1 was not found."


def test_a_run_of_another_site_is_not_found(mock_site_context: Site):
    run = _run_over(make_stub())

    with pytest.raises(Http404):
        run_bulk_action(str(run.pk), mock_site_context.pk + 1000)


def test_the_task_takes_only_the_run_id_and_the_site_id():
    parameters = inspect.signature(_run_bulk_action_task.func).parameters

    assert {name: p.annotation for name, p in parameters.items()} == {
        "run_id": "str",
        "site_id": "int",
    }


def test_the_task_tells_the_action_the_run_finished(mock_site_context: Site):
    run = _run_over(make_stub())

    _run_bulk_action_task.func(str(run.pk), mock_site_context.pk)

    assert StubRecordedBulkAction.finished == [run.pk]


def test_the_task_tells_the_action_about_a_run_that_blew_up(
    mock_site_context: Site, monkeypatch
):
    def _explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("freedom_ls.panel_framework.bulk_runs.run_apply", _explode)
    run = _run_over(make_stub())

    with pytest.raises(RuntimeError):
        _run_bulk_action_task.func(str(run.pk), mock_site_context.pk)

    run.refresh_from_db()
    assert (run.status, StubRecordedBulkAction.finished) == (
        RunStatus.FAILED,
        [run.pk],
    )


def test_an_inline_run_reaches_no_hook(mock_site_context: Site):
    run = _run_over(make_stub())

    run_bulk_action(str(run.pk), mock_site_context.pk)

    assert StubRecordedBulkAction.finished == []


def test_an_unfinished_run_reaches_no_hook(mock_site_context: Site):
    run = _run_over(make_stub())

    report_finished(str(run.pk), mock_site_context.pk)

    assert StubRecordedBulkAction.finished == []


def test_a_run_of_a_removed_action_fails_and_is_marked_so(mock_site_context: Site):
    """An action renamed or removed while a run was queued used to raise before
    the run was marked, leaving it queued forever."""
    run = _run_over(make_stub(), action_path="nowhere.RenamedAway")

    _run_bulk_action_task.func(str(run.pk), mock_site_context.pk)

    run.refresh_from_db()
    assert (run.status, run.error_message) == (RunStatus.FAILED, ACTION_UNAVAILABLE)
    assert run.finished_at is not None


@pytest.mark.parametrize(
    "path",
    [
        "nowhere.RenamedAway",
        "freedom_ls.panel_framework.bulk_actions.BulkAction",
        "freedom_ls.panel_framework.bulk_actions.run_apply",
    ],
)
def test_only_a_recorded_action_class_resolves(mock_site_context: Site, path: str):
    run = _run_over(make_stub(), action_path=path)

    assert action_for(run) is None


def test_the_summary_of_a_done_run_survives_its_action_being_removed(
    mock_site_context: Site,
):
    run = _run_over(make_stub(), action_path="nowhere.RenamedAway")
    run.action_name = "renamed_away"
    run.status = RunStatus.DONE
    run.result = BulkResult(
        counts=[BulkCount("changed", "", 1)], entries=[], left_out=0
    ).to_json()

    assert run_summary(run) == "Renamed away finished: 1 row changed."


def test_the_summary_names_every_kind_of_outcome(mock_site_context: Site):
    run = _run_over(make_stub())
    run.status = RunStatus.DONE
    run.result = BulkResult(
        counts=[
            BulkCount("changed", "", 3),
            BulkCount("skipped", "already inactive", 2),
            BulkCount("skipped", NOT_FOUND, 1),
            BulkCount("failed", "error", 1),
        ],
        entries=[],
        left_out=0,
    ).to_json()

    assert run_summary(run) == (
        "Deactivate finished: 3 stub models changed, 3 skipped, 1 failed."
    )


def test_a_failed_summary_says_where_it_stopped(mock_site_context: Site):
    run = _run_over(make_stub(), GONE)
    run.status, run.processed_count = RunStatus.FAILED, 1

    assert run_summary(run) == "Deactivate stopped after 1 of 2 stub models."
