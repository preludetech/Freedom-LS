"""bulk_run_table_url links a bulk run's notification to the table it ran on."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.notification_urls import bulk_run_table_url
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.models import BulkActionRun


@pytest.mark.django_db
def test_bulk_run_table_url_is_the_runs_table(mock_site_context) -> None:
    organisation = OrganisationFactory()
    run = BulkActionRun.objects.create(
        scope=organisation,
        requested_by=UserFactory(),
        table_key="cohorts",
        action_name="deactivate",
    )

    assert bulk_run_table_url(run) == reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
    )
