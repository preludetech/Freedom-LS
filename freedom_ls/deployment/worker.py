"""Heartbeat and watchdog for the database task worker.

HeartbeatWorker.run() is a copy of django_tasks_db's Worker.run() loop with one
line added. django-tasks-db is pinned exactly (==0.12.0) and a test asserts that
pin, so a version bump fails loudly and this copy gets re-checked.
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from pathlib import Path

import sentry_sdk
from django_tasks_db.management.commands.db_worker import Worker
from django_tasks_db.models import DBTaskResult
from django_tasks_db.utils import exclusive_transaction

from django.db import close_old_connections
from django.db.utils import OperationalError

from freedom_ls.deployment.config import config

# Same logger name db_worker.py uses, so these lines keep whatever destination
# a deployment already has configured for that channel.
logger = logging.getLogger("django_tasks_db")

WATCHDOG_POLL_SECONDS = 30
SENTRY_FLUSH_TIMEOUT_SECONDS = 5


def touch_heartbeat(path: str | Path) -> None:
    """Update the file's mtime, creating it and its parents when absent.

    Only the mtime matters; the contents are never read.
    """
    heartbeat = Path(path)
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.touch()


def heartbeat_age_seconds(path: str | Path) -> float | None:
    """Seconds since the heartbeat's mtime, or None when the file is absent."""
    try:
        mtime = Path(path).stat().st_mtime
    except FileNotFoundError:
        return None
    return time.time() - mtime


def check_worker_heartbeat(path: str | Path, max_age_seconds: int) -> None:
    """One watchdog pass. Reports and kills the process when the heartbeat is stale.

    An absent file counts as stale: fls_run_worker touches the path before the
    watchdog starts, and the external probe's own -mmin window finds nothing either.
    """
    age = heartbeat_age_seconds(path)
    if age is not None and age <= max_age_seconds:
        return
    sentry_sdk.capture_message(
        f"fls_run_worker heartbeat is stale (>{max_age_seconds}s); exiting."
    )
    # Not optional. os._exit skips atexit, and the SDK's automatic drain is an
    # atexit integration, so without this the report is lost in exactly the case
    # that matters.
    sentry_sdk.flush(timeout=SENTRY_FLUSH_TIMEOUT_SECONDS)
    # Not sys.exit(): that raises SystemExit in this thread only and leaves the
    # wedged main thread running.
    os._exit(1)


def start_watchdog(
    path: str | Path,
    max_age_seconds: int,
    poll_seconds: int = WATCHDOG_POLL_SECONDS,
) -> threading.Thread:
    """Start the daemon watchdog thread and return it.

    daemon=True so a clean shutdown is never held open by this thread.
    """

    def _poll_forever() -> None:
        while True:
            time.sleep(poll_seconds)
            check_worker_heartbeat(path, max_age_seconds)

    thread = threading.Thread(target=_poll_forever, daemon=True)
    thread.start()
    return thread


class HeartbeatWorker(Worker):
    """django_tasks_db's Worker with a heartbeat touch on every loop iteration.

    The per-iteration guarantee holds only for batch=False and max_tasks=None:
    upstream's two early-return branches for those options sit before
    close_old_connections(), so a batch worker would stop touching the heartbeat
    the moment its queue drained. fls_run_worker hardcodes both values.
    """

    def run(self) -> None:
        """Copy of django_tasks_db 0.12.0 Worker.run() with a heartbeat touch."""
        logger.info(
            "Starting worker worker_id=%s queues=%s",
            self.worker_id,
            ",".join(self.queue_names),
        )

        if self.startup_delay and self.interval:
            # Add a random small delay before starting to avoid a thundering herd
            time.sleep(random.random())  # noqa: S311

        while self.running:
            tasks = DBTaskResult.objects.ready().filter(backend_name=self.backend_name)
            if not self.process_all_queues:
                tasks = tasks.filter(queue_name__in=self.queue_names)

            # During this transaction, all "ready" tasks are locked. Therefore, it's important
            # it be as efficient as possible.
            with exclusive_transaction(tasks.db):
                try:
                    task_result = tasks.get_locked()
                except OperationalError as e:
                    # Ignore locked databases and keep trying.
                    # It should unlock eventually.
                    if "is locked" in e.args[0]:
                        task_result = None
                    else:
                        raise

                if task_result is not None:
                    # "claim" the task, so it isn't run by another worker process
                    task_result.claim(self.worker_id)

            if task_result is not None:
                self.run_task(task_result)

            if self.batch and task_result is None:
                # If we're running in "batch" mode, terminate the loop (and thus the worker)
                logger.info(
                    "No more tasks to run for worker_id=%s - exiting gracefully.",
                    self.worker_id,
                )
                return None

            if self.max_tasks is not None and self._run_tasks >= self.max_tasks:
                logger.info(
                    "Run maximum tasks (%d) on worker=%s - exiting gracefully.",
                    self._run_tasks,
                    self.worker_id,
                )
                return None

            # Emulate Django's request behaviour and check for expired
            # database connections periodically.
            close_old_connections()

            touch_heartbeat(config.WORKER_HEARTBEAT_PATH)

            # If ctrl-c has just interrupted a task, self.running was cleared,
            # and we should not sleep, but rather exit immediately.
            if self.running and not task_result:
                # Wait before checking for another task
                time.sleep(self.interval)
