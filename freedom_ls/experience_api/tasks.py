"""Django-Tasks task wrapping the Event DB write.

The task receives a fully-resolved payload — every ``_thread_locals`` read
is done in :func:`freedom_ls.experience_api.tracking.track` before enqueue.
Background workers do not have request-bound context so this separation is
mandatory; it is tested explicitly.
"""

from __future__ import annotations

from typing import Any

from django.tasks import task

from .models import Event


@task()
def write_event(payload: dict[str, Any]) -> None:
    """Persist one Event row. Idempotent-by-id but expected to be called once.

    The ``_tracker_authorised`` sentinel authorises the save-override
    guard and is consumed by :py:meth:`Event.save`; it never appears on
    the persisted row.
    """
    instance = Event(**payload)
    instance._tracker_authorised = True
    instance.save()
