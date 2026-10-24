"""The lifecycle shared by every record of a unit of work that may outlive a
request."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from django.utils import timezone

from freedom_ls.learner_management.models import BulkActionRun, RunStatus


@contextmanager
def record_run(record: BulkActionRun) -> Iterator[None]:
    """Mark the record running, then done or failed, stamping the timestamps.

    A try/finally rather than a broad except: the body's own exception still
    propagates to the worker, and a record the body did not mark done is
    marked failed with a generic message so it never stays running forever.
    The body sets `record.status` to done (or to failed with its own
    `error_message`) before it returns.
    """
    record.status, record.started_at = RunStatus.RUNNING, timezone.now()
    record.save(update_fields=["status", "started_at"])
    try:
        yield
    finally:
        if record.status == RunStatus.RUNNING:
            record.status, record.error_message = RunStatus.FAILED, "Unexpected error."
        record.finished_at = timezone.now()
        record.save(update_fields=["status", "error_message", "finished_at", "result"])
