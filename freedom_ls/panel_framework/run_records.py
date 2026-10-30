"""The lifecycle shared by every record of a unit of work that may outlive a
request."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Protocol

from django.utils import timezone

from freedom_ls.panel_framework.models import RunStatus


class RunRecord(Protocol):
    """A model row with the lifecycle fields `record_run` writes."""

    status: str
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None

    def save(self, *, update_fields: list[str] | None = ...) -> None: ...


@contextmanager
def record_run(record: RunRecord, extra_fields: tuple[str, ...] = ()) -> Iterator[None]:
    """Mark the record running, then done or failed, stamping the timestamps.

    A try/finally rather than a broad except: the body's own exception still
    propagates to the worker, and a record the body did not mark done is
    marked failed with a generic message so it never stays running forever.
    The body sets `record.status` to done (or to failed with its own
    `error_message`) before it returns. `extra_fields` names any other fields
    the body sets that the closing save must carry, such as a stored result.
    """
    record.status, record.started_at = RunStatus.RUNNING, timezone.now()
    record.save(update_fields=["status", "started_at"])
    try:
        yield
    finally:
        if record.status == RunStatus.RUNNING:
            record.status, record.error_message = RunStatus.FAILED, "Unexpected error."
        record.finished_at = timezone.now()
        record.save(
            update_fields=["status", "error_message", "finished_at", *extra_fields]
        )
