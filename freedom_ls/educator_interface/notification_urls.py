"""URL builders for notification categories that target educator-interface records."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.urls import reverse

from freedom_ls.organisations.models import Organisation

if TYPE_CHECKING:
    from freedom_ls.panel_framework.models import BulkActionRun


def bulk_run_table_url(run: BulkActionRun) -> str:
    """The table the run was started from. An educator run is always scoped
    to an organisation."""
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cast(Organisation, run.scope).slug,
            "path_string": run.table_key,
        },
    )
