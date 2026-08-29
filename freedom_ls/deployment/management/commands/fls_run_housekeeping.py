"""Run the housekeeping sweeps once and exit."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from freedom_ls.deployment.config import config
from freedom_ls.deployment.housekeeping import run_housekeeping_sweeps
from freedom_ls.deployment.worker import touch_heartbeat


class Command(BaseCommand):
    help = (
        "Prune finished task results, clear expired sessions, and report task "
        "results left unpicked past the configured window. Runs once and exits."
    )

    def handle(self, *args: object, **options: object) -> None:
        failures = run_housekeeping_sweeps()
        if failures:
            raise CommandError("; ".join(failures))
        # Only a fully clean run counts as a heartbeat: both sweeps succeeded and
        # nothing was left unpicked.
        touch_heartbeat(config.HOUSEKEEPING_HEARTBEAT_PATH)
        self.stdout.write("Housekeeping complete.")
