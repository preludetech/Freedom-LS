"""`BulkActionRun`: the one row the framework keeps, and the scope lookup
hosts filter it by."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site

from freedom_ls.panel_framework.models import BulkActionRun, RunStatus, scope_lookup
from freedom_ls.tests.factories import SiteFactory

from .helpers import make_staff_user, make_stub

pytestmark = pytest.mark.django_db

ACTION_PATH = "panel_framework.tests.stub_panels.StubRecordedBulkAction"


def _run(**fields: object) -> BulkActionRun:
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            requested_by=make_staff_user(),
            action_path=ACTION_PATH,
            table_key="stubs",
            action_name="stub_recorded",
            **fields,
        ),
    )


def test_a_run_takes_its_site_from_the_ambient_site(mock_site_context: Site):
    run = _run()

    assert run.site == mock_site_context


def test_the_default_manager_hides_another_sites_runs(mock_site_context: Site):
    BulkActionRun._base_manager.create(
        site=SiteFactory(),
        requested_by=make_staff_user(),
        action_path=ACTION_PATH,
        table_key="stubs",
        action_name="stub_recorded",
    )

    assert not BulkActionRun.objects.exists()


def test_a_new_run_is_queued_with_no_progress(mock_site_context: Site):
    run = _run()

    assert (run.status, run.processed_count, run.result) == (
        RunStatus.QUEUED,
        0,
        None,
    )


def test_a_run_records_the_scope_it_was_started_under(mock_site_context: Site):
    scope = make_stub()

    run = _run(scope=scope)

    assert BulkActionRun.objects.get(pk=run.pk).scope == scope


def test_the_scope_lookup_finds_runs_of_one_scope_only(mock_site_context: Site):
    here, elsewhere = make_stub(), make_stub()
    run = _run(scope=here)
    _run(scope=elsewhere)
    _run()

    assert list(BulkActionRun.objects.filter(**scope_lookup(here))) == [run]


def test_the_scope_lookup_for_no_scope_finds_only_unscoped_runs(
    mock_site_context: Site,
):
    _run(scope=make_stub())
    unscoped = _run()

    assert list(BulkActionRun.objects.filter(**scope_lookup(None))) == [unscoped]
