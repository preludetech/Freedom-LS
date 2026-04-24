"""``maintain_event_partitions`` management command.

Partition activation is deferred (see spec §"Partition maintenance"). The
command ships now so activation is a single operator step later. When the
events table is not partitioned — the current state — the command logs a
structured warning and exits 0. Operator-facing CLI flags are accepted
and validated so automation (cron) does not need to change when
activation happens.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Create upcoming partitions and (optionally) drop expired partitions "
        "for the Event table. No-op when the table is not partitioned."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--lookahead-months", type=int, default=3)
        parser.add_argument("--retention-months", type=int, default=24)
        parser.add_argument("--drop-old", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options) -> None:
        # TODO: implement activation when the events table becomes partitioned
        # (see spec §"Partition maintenance"). Until then, this command is a
        # structured no-op so operator automation (cron) can be wired now and
        # does not need to change when partitioning lands.
        lookahead = options["lookahead_months"]
        retention = options["retention_months"]
        drop_old = options["drop_old"]
        dry_run = options["dry_run"]

        partitioned = self._table_is_partitioned("experience_api_event")
        if not partitioned:
            message = (
                "experience_api_event is not partitioned; "
                "maintain_event_partitions is a no-op. "
                f"(lookahead_months={lookahead}, retention_months={retention}, "
                f"drop_old={drop_old}, dry_run={dry_run})"
            )
            logger.warning(message)
            self.stdout.write(message)
            return

        logger.info(
            "maintain_event_partitions: partitioned-table branch not "
            "yet implemented (lookahead=%s, retention=%s, drop=%s, dry=%s)",
            lookahead,
            retention,
            drop_old,
            dry_run,
        )

    def _table_is_partitioned(self, table_name: str) -> bool:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_partitioned_table pp "
                "JOIN pg_class c ON c.oid = pp.partrelid "
                "WHERE c.relname = %s",
                [table_name],
            )
            return cursor.fetchone() is not None
