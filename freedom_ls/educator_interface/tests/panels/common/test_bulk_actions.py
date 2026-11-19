"""Tests for the educator bulk-action base: the organisation scope and the finished notification."""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.models import Notification
from freedom_ls.educator_interface.actions import DeactivateLearnersBulkAction
from freedom_ls.educator_interface.tests.helpers import (
    _bulk_learner,
    _bulk_post,
    _bulk_text,
    _learners_bulk_url,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import Learner
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.bulk_actions import BulkCount, BulkResult
from freedom_ls.panel_framework.bulk_runs import (
    NOT_FOUND,
    report_finished,
    run_bulk_action,
    run_summary,
)
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus

GONE = "00000000-0000-0000-0000-000000000001"
DEACTIVATE = (
    f"{DeactivateLearnersBulkAction.__module__}.{DeactivateLearnersBulkAction.__name__}"
)


def _learner() -> Learner:
    return cast(Learner, LearnerFactory(organisation=OrganisationFactory()))


def _run_over(learner: Learner, *others: str) -> BulkActionRun:
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            site=learner.organisation.site,
            scope=learner.organisation,
            requested_by=UserFactory(superuser=True),
            action_path=DEACTIVATE,
            table_key="learners",
            action_name="deactivate",
            keys=[str(learner.pk), *others],
        ),
    )


@pytest.mark.django_db
def test_a_learner_of_another_organisation_is_not_touched(mock_site_context: Site):
    other = _learner()
    run = _run_over(_learner(), str(other.pk))

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    other.refresh_from_db()
    assert other.is_active is True
    assert BulkCount("skipped", NOT_FOUND, 1) in result.counts


@pytest.mark.django_db
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


def _run_in_background(run: BulkActionRun, site: Site) -> None:
    """Run as the background task does: a finished run is reported back."""
    run_bulk_action(
        str(run.pk),
        site.pk,
        on_finished=lambda closed: report_finished(str(closed.pk), closed.site_id),
    )


@pytest.mark.django_db
def test_the_task_tells_the_requester_the_run_finished(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner(), GONE)

    with django_capture_on_commit_callbacks(execute=True):
        _run_in_background(run, mock_site_context)

    assert _notifications_for(run) == [
        (run.requested_by_id, "Deactivate finished: 1 learner changed, 1 skipped.")
    ]


@pytest.mark.django_db
def test_the_task_tells_the_requester_where_a_failed_run_stopped(
    mock_site_context: Site, django_capture_on_commit_callbacks, monkeypatch
):
    def _explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("freedom_ls.panel_framework.bulk_runs.run_apply", _explode)
    run = _run_over(_learner())

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(RuntimeError),
    ):
        _run_in_background(run, mock_site_context)

    assert _notifications_for(run) == [
        (run.requested_by_id, "Deactivate stopped after 0 of 1 learner.")
    ]


@pytest.mark.django_db
def test_an_inline_run_raises_no_notification(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner())

    with django_capture_on_commit_callbacks(execute=True):
        run_bulk_action(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == []


@pytest.mark.django_db
def test_an_unfinished_run_is_not_notified(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner())

    with django_capture_on_commit_callbacks(execute=True):
        report_finished(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == []


@pytest.mark.django_db
def test_the_summary_counts_in_the_actions_own_noun(mock_site_context: Site):
    run = _run_over(_learner())
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
        "Deactivate finished: 3 learners changed, 3 skipped, 1 failed."
    )


@pytest.mark.django_db
@pytest.mark.parametrize("action_name", ["register_for_course", "add_to_cohort"])
def test_a_bulk_action_on_rows_that_left_the_scope_answers_the_unavailable_dialog(
    staff_client: Client, action_name: str
):
    """Ticked rows the educator can no longer see are a 404, like a single-row
    action on them, with the same body as for a row that never existed."""
    organisation = OrganisationFactory()
    elsewhere = _bulk_learner(organisation=OrganisationFactory())

    gone = _bulk_post(staff_client, organisation, action_name, [elsewhere])
    never = staff_client.post(
        _learners_bulk_url(organisation, action_name),
        {"keys": [str(uuid.uuid4())]},
        HTTP_HX_REQUEST="true",
    )

    assert gone.status_code == 404
    assert "This is no longer available" in _bulk_text(gone)
    assert gone.content == never.content
