"""Heartbeat and watchdog for the database task worker.

HeartbeatWorker.run() is a copy of django_tasks_db's Worker.run() loop with one
line added. django-tasks-db is pinned exactly (==0.12.0) and a test asserts that
pin, so a version bump fails loudly and this copy gets re-checked.

HeartbeatWorker.run_task() is an override, not part of that copy: upstream's loop
calls self.run_task, so holding the heartbeat up for the duration of a long task
needs no further change to the copied body.
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
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
# How often the ticker holds the heartbeat up during a task. An order of magnitude
# inside the default WORKER_HEARTBEAT_MAX_AGE_SECONDS, which a config test pins.
HEARTBEAT_TICK_SECONDS = 30
TICKER_JOIN_TIMEOUT_SECONDS = 5


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
    # The exit is in a finally so that a Sentry call raising cannot leave the
    # wedged worker running: reporting the stall is worth attempting, but ending
    # the process is the part that must happen. No except clause is needed, and
    # none is wanted -- os._exit never returns, so nothing propagates past here.
    try:
        sentry_sdk.capture_message(
            f"fls_run_worker heartbeat is stale (>{max_age_seconds}s); exiting."
        )
        # Not optional. os._exit skips atexit, and the SDK's automatic drain is an
        # atexit integration, so without this the report is lost in exactly the
        # case that matters.
        sentry_sdk.flush(timeout=SENTRY_FLUSH_TIMEOUT_SECONDS)
    finally:
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
            try:
                check_worker_heartbeat(path, max_age_seconds)
            except OSError:
                # stat() can fail for reasons other than the file being absent --
                # a mode change on the parent directory, a full or read-only
                # filesystem. Unguarded, that ends this thread and the worker runs
                # on with no watchdog at all, silently, in exactly the situation
                # the watchdog exists for. One bad poll is not evidence the loop
                # has stalled, so keep polling.
                logger.exception("Watchdog heartbeat check failed; still polling.")

    thread = threading.Thread(target=_poll_forever, daemon=True)
    thread.start()
    return thread


def touch_until_capped(
    path: str | Path,
    stop: threading.Event,
    deadline: float,
    tick_seconds: float,
) -> None:
    """Hold the heartbeat up on the ticker thread until stopped or past `deadline`.

    `stop.wait(...)` rather than `time.sleep(...)`: the caller's finally ends this
    thread at once instead of at the end of whatever tick it is sitting in.

    `deadline` is an absolute monotonic time, not a duration, so the cap runs from
    the moment the task was handed over rather than from whenever this thread was
    first scheduled.

    Past the deadline it stops touching deliberately. The heartbeat then ages out
    and the watchdog ends the process, which is what bounds a genuinely hung task.
    It catches nothing for the same reason: an OSError from a full or read-only
    disk should stop the touching, and the watchdog handles what follows.
    """
    while not stop.wait(tick_seconds):
        if time.monotonic() >= deadline:
            return
        touch_heartbeat(path)


@contextmanager
def heartbeat_ticker(
    path: str | Path,
    max_seconds: int,
    tick_seconds: float = HEARTBEAT_TICK_SECONDS,
) -> Iterator[None]:
    """Keep the heartbeat fresh while the block runs, for at most `max_seconds`.

    daemon=True matches start_watchdog: neither a clean shutdown nor the watchdog's
    own os._exit is ever held open by this thread.

    The join is what makes stopping deterministic — the thread is gone before the
    caller returns, so nothing left over from one task can touch the heartbeat
    during the next. It is bounded so that a wedged filesystem cannot in turn wedge
    the work loop.

    The thread must never touch the database: it would open a connection of its own
    that the work loop's close_old_connections() never closes.
    """
    stop = threading.Event()
    deadline = time.monotonic() + max_seconds
    thread = threading.Thread(
        target=touch_until_capped,
        kwargs={
            "path": path,
            "stop": stop,
            "deadline": deadline,
            "tick_seconds": tick_seconds,
        },
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=TICKER_JOIN_TIMEOUT_SECONDS)


class HeartbeatWorker(Worker):
    """django_tasks_db's Worker with a heartbeat touch on every loop iteration.

    The heartbeat is held up in two places, covering the two things that can be
    happening: the touch at the bottom of the loop covers the gaps between tasks,
    and run_task's ticker covers the time inside one. Without the second, a single
    task longer than WORKER_HEARTBEAT_MAX_AGE_SECONDS lets the watchdog kill the
    worker in the middle of legitimate work.

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

    def run_task(self, db_task_result: DBTaskResult) -> None:
        """Run one task with the heartbeat held up for it, up to the configured cap.

        Upstream's run() calls self.run_task, so this needs no change to the copied
        loop above. The touch at the bottom of that loop only fires between tasks,
        which left any task longer than WORKER_HEARTBEAT_MAX_AGE_SECONDS to be
        killed mid-flight — taking its unfinished bookkeeping with it, since
        os._exit runs no finally blocks.
        """
        with heartbeat_ticker(
            config.WORKER_HEARTBEAT_PATH,
            max_seconds=config.WORKER_MAX_TASK_SECONDS,
        ):
            super().run_task(db_task_result)
