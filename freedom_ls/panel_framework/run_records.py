"""The lifecycle shared by every record of a unit of work that may outlive a
request."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Protocol

from django.db.models import Model, QuerySet
from django.utils import timezone

from freedom_ls.panel_framework.models import RunStatus


class RunRecord(Protocol):
    """A model row with the lifecycle fields `record_run` writes."""

    status: str
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None


def claim_run[T: Model](records: QuerySet[T]) -> T | None:
    """The queued record `records` names, now marked running, or None when it
    is not queued: a sweep closed it before a worker took its task, or another
    worker already holds it. One conditional update, so two workers handed the
    same task can only claim it once."""
    claimed = records.filter(status=RunStatus.QUEUED).update(
        status=RunStatus.RUNNING, started_at=timezone.now()
    )
    return records.get() if claimed else None


@contextmanager
def record_run[T: RunRecord](
    record: T,
    records: QuerySet,
    extra_fields: tuple[str, ...] = (),
    on_closed: Callable[[T], None] | None = None,
) -> Iterator[None]:
    """Mark a claimed record done or failed, stamping finished_at.

    A try/finally rather than a broad except: the body's own exception still
    propagates to the worker, and a record the body did not mark done is
    marked failed with a generic message so it never stays running forever.
    The body sets `record.status` to done (or to failed with its own
    `error_message`) before it returns. `extra_fields` names any other fields
    the body sets that the closing save must carry, such as a stored result.

    `records` names `record` and nothing else; the closing save is a
    conditional update through it, so a sweep that closed the record first
    keeps its verdict. `on_closed` is called only when this process closed the
    record: a record the sweep closed was reported by the sweep.
    """
    if record.status != RunStatus.RUNNING:
        raise ValueError("record_run needs a record claim_run has claimed.")
    try:
        yield
    finally:
        if record.status == RunStatus.RUNNING:
            record.status, record.error_message = RunStatus.FAILED, "Unexpected error."
        record.finished_at = timezone.now()
        closed = records.filter(status=RunStatus.RUNNING).update(
            status=record.status,
            error_message=record.error_message,
            finished_at=record.finished_at,
            **{field: getattr(record, field) for field in extra_fields},
        )
        if closed and on_closed is not None:
            on_closed(record)
