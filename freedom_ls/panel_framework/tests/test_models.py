"""`BulkActionRun`: the one row the framework keeps, and the scope lookup
hosts filter it by."""

from __future__ import annotations

from typing import cast

import pytest
from pytest_django.fixtures import SettingsWrapper

from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.db import IntegrityError, models, transaction
from django.http import HttpRequest
from django.test import RequestFactory, override_settings

from freedom_ls.panel_framework.models import BulkActionRun, RunStatus, scope_lookup

from .helpers import make_site, make_staff_user, make_stub

pytestmark = pytest.mark.django_db

ACTION_PATH = "panel_framework.tests.stub_panels.StubRecordedBulkAction"


def request_site(request: HttpRequest) -> RequestSite:
    """A stand-in resolver that answers with something that is not a Site row."""
    return RequestSite(request)


def _request(host: str = "testserver") -> HttpRequest:
    return RequestFactory().get("/", HTTP_HOST=host)


def _run(site: Site, **fields: object) -> BulkActionRun:
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            site=site,
            requested_by=make_staff_user(site),
            action_path=ACTION_PATH,
            table_key="stubs",
            action_name="stub_recorded",
            **fields,
        ),
    )


def test_for_site_returns_only_that_sites_runs(mock_site_context: Site):
    other = make_site("Other", "other.test")
    here = _run(mock_site_context)
    _run(other)

    assert list(BulkActionRun.objects.for_site(mock_site_context.pk)) == [here]


def test_for_request_returns_only_the_request_sites_runs(mock_site_context: Site):
    here = _run(mock_site_context)
    _run(make_site("Other", "other.test"))

    assert list(BulkActionRun.objects.for_request(_request())) == [here]


def test_for_request_returns_no_runs_when_the_resolver_returns_a_non_site(
    mock_site_context: Site,
):
    _run(mock_site_context)

    with override_settings(PANEL_FRAMEWORK_SITE_RESOLVER=f"{__name__}.request_site"):
        runs = list(BulkActionRun.objects.for_request(_request()))

    assert runs == []


@override_settings(SITE_ID=None, ALLOWED_HOSTS=["*"])
def test_for_request_returns_no_runs_for_an_unknown_host_under_the_default_resolver(
    settings: SettingsWrapper,
):
    _run(make_site("Other", "other.test"))
    del settings.PANEL_FRAMEWORK_SITE_RESOLVER

    assert list(BulkActionRun.objects.for_request(_request("unknown.test"))) == []


def test_a_run_saved_without_a_site_is_refused(mock_site_context: Site):
    with pytest.raises(IntegrityError), transaction.atomic():
        BulkActionRun.objects.create(
            requested_by=make_staff_user(),
            action_path=ACTION_PATH,
            table_key="stubs",
            action_name="stub_recorded",
        )


def test_a_run_inherits_nothing_from_the_site_aware_models_app():
    modules = {base.__module__ for base in BulkActionRun.__mro__}

    assert not any(
        module.startswith("freedom_ls.site_aware_models") for module in modules
    )


def test_the_base_manager_is_djangos_plain_manager():
    assert type(BulkActionRun._base_manager) is models.Manager


def test_a_new_run_is_queued_with_no_progress(mock_site_context: Site):
    run = _run(mock_site_context)

    assert (run.status, run.processed_count, run.result) == (
        RunStatus.QUEUED,
        0,
        None,
    )


def test_a_run_records_the_scope_it_was_started_under(mock_site_context: Site):
    scope = make_stub()

    run = _run(mock_site_context, scope=scope)

    assert BulkActionRun.objects.get(pk=run.pk).scope == scope


def test_the_scope_lookup_finds_runs_of_one_scope_only(mock_site_context: Site):
    here, elsewhere = make_stub(), make_stub()
    run = _run(mock_site_context, scope=here)
    _run(mock_site_context, scope=elsewhere)
    _run(mock_site_context)

    assert list(BulkActionRun.objects.filter(**scope_lookup(here))) == [run]


def test_the_scope_lookup_for_no_scope_finds_only_unscoped_runs(
    mock_site_context: Site,
):
    _run(mock_site_context, scope=make_stub())
    unscoped = _run(mock_site_context)

    assert list(BulkActionRun.objects.filter(**scope_lookup(None))) == [unscoped]
