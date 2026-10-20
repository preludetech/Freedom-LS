"""Collection gate for an app a project may leave out of INSTALLED_APPS."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import pytest

from django.db import connection

from freedom_ls.tests.app_guards import app_not_installed

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.registration_rules"):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture
def django_capture_on_commit_callbacks(
    django_capture_on_commit_callbacks: Callable[
        ..., AbstractContextManager[list[Callable[[], object]]]
    ],
) -> Callable[..., AbstractContextManager[list[Callable[[], object]]]]:
    """pytest-django's fixture, treating the Arrange step as committed.

    The test transaction never commits, so callbacks the Arrange step queued
    stay pending. The signals queue each evaluation once per transaction, so a
    pending one would swallow the identical callback the Act step queues.
    Entering the block drops them, as a real commit would have run them.
    """

    @contextmanager
    def capture(**kwargs: object) -> Iterator[list[Callable[[], object]]]:
        connection.run_on_commit.clear()
        with django_capture_on_commit_callbacks(**kwargs) as callbacks:
            yield callbacks

    return capture
