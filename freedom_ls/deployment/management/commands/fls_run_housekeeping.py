"""Run the housekeeping sweeps once and exit."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from freedom_ls.deployment.config import config
from freedom_ls.deployment.housekeeping import run_housekeeping_sweeps
from freedom_ls.deployment.worker import touch_heartbeat


class Command(BaseCommand):
    help = (
        "Prune finished task results, clear expired sessions, report task results "
        "left unpicked past the configured window, and close any task result still "
        "claimed past the configured window. Runs once and exits."
    )

    def handle(self, *args: object, **options: object) -> None:
        outcome = run_housekeeping_sweeps()

        for note in outcome.notes:
            self.stdout.write(note)

        # A heartbeat covers only this container's own work. A stalled queue and a
        # worker that died holding a task are both faults elsewhere, so a finding
        # leaves this heartbeat standing and only housekeeping's own sweeps failing
        # withholds it. Touched before the raise, or the finding branch never
        # reaches it.
        if not outcome.sweep_failures:
            touch_heartbeat(config.HOUSEKEEPING_HEARTBEAT_PATH)

        if outcome.sweep_failures or outcome.findings:
            raise CommandError(outcome.failure_message())

        self.stdout.write("Housekeeping complete.")
