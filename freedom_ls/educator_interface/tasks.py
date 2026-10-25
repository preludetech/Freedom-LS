"""Background tasks of the educator interface.

The task queue serialises only primitive, JSON-safe arguments, so each task
is a thin wrapper that hands plain ids to a function that can also run inline.
"""

from __future__ import annotations

from django.tasks import task

from freedom_ls.educator_interface.bulk_runs import (
    notify_run_finished,
    run_bulk_action,
)
from freedom_ls.educator_interface.learner_import import run_learner_import


@task()
def _run_bulk_action_task(run_id: str, site_id: int) -> None:
    # Only a background run notifies: an inline one reports in the modal of
    # the request that ran it.
    try:
        run_bulk_action(run_id, site_id)
    finally:
        notify_run_finished(run_id, site_id)


@task()
def _run_learner_import_task(import_id: str, site_id: int) -> None:
    run_learner_import(import_id, site_id)
