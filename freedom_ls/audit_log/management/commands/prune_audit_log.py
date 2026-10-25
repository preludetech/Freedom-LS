"""Delete audit log entries older than a number of days."""

from datetime import timedelta

import djclick as click

from django.utils import timezone

from freedom_ls.audit_log.config import config
from freedom_ls.audit_log.models import AuditLogEntry


@click.command()
@click.option(
    "--older-than",
    "older_than",
    type=click.IntRange(min=1),
    default=None,
    help="Delete entries older than this many days.",
)
@click.option("--dry-run", is_flag=True, help="Report the count without deleting.")
def command(older_than: int | None, dry_run: bool) -> None:
    """Delete audit log entries older than --older-than days, or than AUDIT_LOG_RETENTION_DAYS."""
    days = older_than if older_than is not None else config.AUDIT_LOG_RETENTION_DAYS
    if days is None or days < 1:
        raise click.ClickException(
            "Give --older-than DAYS (at least 1) or set AUDIT_LOG_RETENTION_DAYS."
        )
    cutoff = timezone.now() - timedelta(days=days)
    if dry_run:
        count = AuditLogEntry.unscoped.filter(created_at__lt=cutoff).count()
        click.echo(f"Would delete {count} entries.")
        return
    click.echo(f"Deleted {AuditLogEntry.unscoped.all().prune_before(cutoff)} entries.")
