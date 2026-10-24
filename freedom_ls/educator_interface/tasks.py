"""Background tasks of the educator interface.

The task queue serialises only primitive, JSON-safe arguments, so each task
is a thin wrapper that hands plain ids to a function that can also run inline.
"""

from __future__ import annotations

from django.tasks import task

from freedom_ls.educator_interface.bulk_runs import run_bulk_action


@task()
def _run_bulk_action_task(run_id: str, site_id: int) -> None:
    run_bulk_action(run_id, site_id)
