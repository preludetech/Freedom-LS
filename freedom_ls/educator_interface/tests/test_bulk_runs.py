"""`run_bulk_action`: a recorded bulk action run from nothing but its id, and
the notification a background run raises when it finishes."""

from __future__ import annotations

import inspect
from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.http import Http404

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.models import Notification
from freedom_ls.educator_interface.bulk_runs import (
    NO_LONGER_EXISTS,
    notify_run_finished,
    run_bulk_action,
    run_summary,
)
from freedom_ls.educator_interface.tasks import _run_bulk_action_task
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import BulkActionRun, Learner, RunStatus
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.bulk_actions import BulkCount, BulkResult
from freedom_ls.tests.site_context import drop_ambient_request

pytestmark = pytest.mark.django_db

GONE = "00000000-0000-0000-0000-000000000001"


def _learner() -> Learner:
    return cast(Learner, LearnerFactory(organisation=OrganisationFactory()))


def _run_over(learner: Learner, *others: str) -> BulkActionRun:
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            organisation=learner.organisation,
            requested_by=UserFactory(superuser=True),
            table_key="learners",
            action_name="deactivate",
            keys=[str(learner.pk), *others],
        ),
    )


def test_it_resolves_the_run_with_no_ambient_site(mock_site_context: Site):
    learner = _learner()
    run = _run_over(learner)
    drop_ambient_request()

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    learner.refresh_from_db()
    assert (result.changed, learner.is_active) == (1, False)


def test_it_stores_the_result_json_and_marks_the_run_done(mock_site_context: Site):
    run = _run_over(_learner())

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    run = BulkActionRun._base_manager.get(pk=run.pk)
    assert run.status == RunStatus.DONE
    assert run.result == result.to_json()
    assert run.finished_at is not None


def test_a_stale_key_is_reported_as_no_longer_existing(mock_site_context: Site):
    run = _run_over(_learner(), GONE)

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    assert BulkCount("skipped", NO_LONGER_EXISTS, 1) in result.counts
    assert [(entry.key, entry.reason) for entry in result.entries] == [
        (GONE, NO_LONGER_EXISTS)
    ]


def test_a_learner_of_another_organisation_is_not_touched(mock_site_context: Site):
    other = _learner()
    run = _run_over(_learner(), str(other.pk))

    run_bulk_action(str(run.pk), mock_site_context.pk)

    other.refresh_from_db()
    assert other.is_active is True


def test_a_run_of_another_site_is_not_found(mock_site_context: Site):
    run = _run_over(_learner())

    with pytest.raises(Http404):
        run_bulk_action(str(run.pk), mock_site_context.pk + 1000)


def test_the_task_takes_only_the_run_id_and_the_site_id():
    parameters = inspect.signature(_run_bulk_action_task.func).parameters

    assert {name: p.annotation for name, p in parameters.items()} == {
        "run_id": "str",
        "site_id": "int",
    }


def test_a_requester_who_lost_the_grant_skips_every_object_and_the_run_is_done(
    mock_site_context: Site,
):
    learner = _learner()
    run = _run_over(learner)
    run.requested_by = UserFactory(staff=True)
    run.save(update_fields=["requested_by"])

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    learner.refresh_from_db()
    run.refresh_from_db()
    assert (result.changed, learner.is_active, run.status) == (
        0,
        True,
        RunStatus.DONE,
    )
    assert [item.reason for item in result.counts] == [
        "learners you don't have permission to change"
    ]


def _notifications_for(run: BulkActionRun) -> list[tuple[int, str]]:
    return [
        (notification.user_id, notification.message)
        for notification in Notification._base_manager.filter(
            category="bulk_action.finished", object_id=str(run.pk)
        )
    ]


def test_the_task_tells_the_requester_the_run_finished(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner(), GONE)

    with django_capture_on_commit_callbacks(execute=True):
        _run_bulk_action_task.func(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == [
        (run.requested_by_id, "Deactivate finished: 1 learner changed, 1 skipped.")
    ]


def test_the_task_tells_the_requester_where_a_failed_run_stopped(
    mock_site_context: Site, django_capture_on_commit_callbacks, monkeypatch
):
    def _explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("freedom_ls.educator_interface.bulk_runs.run_apply", _explode)
    run = _run_over(_learner())

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(RuntimeError),
    ):
        _run_bulk_action_task.func(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == [
        (run.requested_by_id, "Deactivate stopped after 0 of 1 learner.")
    ]


def test_an_inline_run_raises_no_notification(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner())

    with django_capture_on_commit_callbacks(execute=True):
        run_bulk_action(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == []


def test_an_unfinished_run_is_not_notified(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner())

    with django_capture_on_commit_callbacks(execute=True):
        notify_run_finished(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == []


def test_the_summary_names_every_kind_of_outcome(mock_site_context: Site):
    run = _run_over(_learner())
    run.status = RunStatus.DONE
    run.result = BulkResult(
        counts=[
            BulkCount("changed", "", 3),
            BulkCount("skipped", "already inactive", 2),
            BulkCount("skipped", NO_LONGER_EXISTS, 1),
            BulkCount("failed", "error", 1),
        ],
        entries=[],
        left_out=0,
    ).to_json()

    assert run_summary(run) == (
        "Deactivate finished: 3 learners changed, 3 skipped, 1 failed."
    )
