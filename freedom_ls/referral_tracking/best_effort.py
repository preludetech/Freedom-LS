"""A guard for writes that must never fail the request they ride on."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import sentry_sdk

from django.db import DatabaseError, transaction


@contextmanager
def best_effort_write() -> Iterator[None]:
    """Run a write that must never fail the request it rides on.

    The savepoint keeps a failed INSERT from poisoning the caller's transaction;
    the failure is reported rather than retried, so a lost write stays lost.
    """
    try:
        with transaction.atomic():
            yield
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
