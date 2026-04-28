"""``maintain_event_partitions`` management command.

Partition activation is deferred (see spec §"Partition maintenance"). The
command ships now so activation is a single operator step later. When the
events table is not partitioned — the current state — the command logs a
structured no-op message at INFO and exits 0. Operator-facing CLI flags
are accepted and validated so automation (cron) does not need to change
when activation happens.
"""

from __future__ import annotations

import logging

import djclick as click

from django.db import connection

logger = logging.getLogger(__name__)


def _table_is_partitioned(table_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_partitioned_table pp "
            "JOIN pg_class c ON c.oid = pp.partrelid "
            "WHERE c.relname = %s",
            [table_name],
        )
        return cursor.fetchone() is not None


@click.command()
@click.option("--lookahead-months", type=int, default=3)
@click.option("--retention-months", type=int, default=24)
@click.option("--drop-old", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False)
def command(
    lookahead_months: int,
    retention_months: int,
    drop_old: bool,
    dry_run: bool,
) -> None:
    """Create upcoming partitions and (optionally) drop expired partitions."""
    # TODO: implement activation when the events table becomes partitioned
    # (see spec §"Partition maintenance"). Until then, this command is a
    # structured no-op so operator automation (cron) can be wired now and
    # does not need to change when partitioning lands.
    partitioned = _table_is_partitioned("experience_api_event")
    if not partitioned:
        # INFO (not WARNING) — the no-op is expected while the events
        # table is not yet partitioned; alerting on every cron run
        # would spam monitoring dashboards.
        message = (
            "experience_api_event is not partitioned; "
            "maintain_event_partitions is a no-op. "
            f"(lookahead_months={lookahead_months}, "
            f"retention_months={retention_months}, "
            f"drop_old={drop_old}, dry_run={dry_run})"
        )
        logger.info(message)
        click.echo(message)
        return

    logger.info(
        "maintain_event_partitions: partitioned-table branch not "
        "yet implemented (lookahead=%s, retention=%s, drop=%s, dry=%s)",
        lookahead_months,
        retention_months,
        drop_old,
        dry_run,
    )
