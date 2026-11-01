"""URL builders for notification categories that target educator-interface records."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.urls import reverse

from freedom_ls.organisations.models import Organisation

if TYPE_CHECKING:
    from freedom_ls.panel_framework.models import BulkActionRun


def bulk_run_table_url(run: BulkActionRun) -> str | None:
    """The table the run was started from. An educator run is always scoped
    to an organisation; None once that organisation has been deleted, since
    nothing cascades to the run and there is no table left to link."""
    if run.scope is None:
        return None
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cast(Organisation, run.scope).slug,
            "path_string": run.table_key,
        },
    )
