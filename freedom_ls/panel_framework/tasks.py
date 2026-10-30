"""Background tasks of the panel framework.

The task queue serialises only primitive, JSON-safe arguments, so the task is
a thin wrapper that hands plain ids to a function that can also run inline.
"""

from __future__ import annotations

from django.tasks import task

from freedom_ls.panel_framework.bulk_runs import report_finished, run_bulk_action


@task()
def _run_bulk_action_task(run_id: str, site_id: int) -> None:
    # Only a background run reports back: an inline one shows its result in
    # the modal of the request that ran it.
    try:
        run_bulk_action(run_id, site_id)
    finally:
        report_finished(run_id, site_id)
