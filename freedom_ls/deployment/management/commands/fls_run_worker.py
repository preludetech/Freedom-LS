"""Run the database task worker with a heartbeat and a watchdog."""

from __future__ import annotations

from django_tasks import DEFAULT_TASK_BACKEND_ALIAS
from django_tasks.utils import get_random_id

from django.core.management.base import BaseCommand

from freedom_ls.deployment.config import config
from freedom_ls.deployment.worker import (
    HeartbeatWorker,
    start_watchdog,
    touch_heartbeat,
)


class Command(BaseCommand):
    help = (
        "Run the database task worker with a heartbeat file and a watchdog that "
        "exits the process when the work loop stalls. Anyone needing the full flag "
        "surface runs db_worker."
    )

    def handle(self, *args: object, **options: object) -> None:
        heartbeat_path = config.WORKER_HEARTBEAT_PATH
        touch_heartbeat(heartbeat_path)
        start_watchdog(heartbeat_path, config.WORKER_HEARTBEAT_MAX_AGE_SECONDS)

        worker = HeartbeatWorker(
            queue_names=[
                "*"
            ],  # every queue; db_worker's own default is "default" alone
            interval=1,
            batch=False,
            backend_name=DEFAULT_TASK_BACKEND_ALIAS,
            startup_delay=True,
            max_tasks=None,
            worker_id=get_random_id(),
        )
        worker.configure_signals()
        worker.run()
