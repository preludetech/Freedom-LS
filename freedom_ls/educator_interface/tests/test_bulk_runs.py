"""`run_bulk_action`: a recorded bulk action run from nothing but its id."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.http import Http404

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.bulk_runs import (
    NO_LONGER_EXISTS,
    run_bulk_action,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import BulkActionRun, Learner, RunStatus
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.bulk_actions import BulkCount
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
