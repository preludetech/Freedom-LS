"""URL builders for notification categories that target educator-interface records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse

if TYPE_CHECKING:
    from freedom_ls.learner_management.models import BulkActionRun


def bulk_run_table_url(run: BulkActionRun) -> str:
    """The table the run was started from."""
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": run.organisation.slug,
            "path_string": run.table_key,
        },
    )
