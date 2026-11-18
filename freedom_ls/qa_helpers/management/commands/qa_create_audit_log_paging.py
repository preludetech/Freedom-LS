"""Fill an organisation's Audit log with enough entries to page.

Toggles each existing cohort in the organisation off and back on through the
real services (deactivate_cohort / reactivate_cohort), so every toggle writes
one "Cohort deactivated" or "Cohort reactivated" entry and each cohort ends in
the state it started in. Every --reason-every-th entry carries a reason, which
gives its row a detail on the Audit log table.

Audit entries are append-only: each run adds 2 x --pairs x (number of cohorts)
more entries.

Usage:
    uv run python manage.py qa_create_audit_log_paging
    uv run python manage.py qa_create_audit_log_paging --organisation-slug demodev --pairs 6
"""

from __future__ import annotations

import djclick as click

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.learner_management.learner_actions import (
    deactivate_cohort,
    reactivate_cohort,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.models import Organisation

REASONS = (
    "Paused while the facilitator is on leave",
    "Course materials under review",
    "Resumed after the timetable was confirmed",
    "Registrar asked for a temporary hold",
)


@click.command()
@click.option("--organisation-slug", default="demodev", show_default=True)
@click.option("--actor-email", default="demodev@email.com", show_default=True)
@click.option(
    "--pairs",
    default=6,
    show_default=True,
    help="Off-and-on toggles per cohort; each toggle writes two entries.",
)
@click.option(
    "--reason-every",
    default=3,
    show_default=True,
    help="Give every Nth entry a reason (a row detail).",
)
def command(
    organisation_slug: str, actor_email: str, pairs: int, reason_every: int
) -> None:
    organisation = Organisation._base_manager.get(slug=organisation_slug)
    actor = User._base_manager.get(email=actor_email, site=organisation.site)
    cohorts = list(
        Cohort._base_manager.filter(organisation=organisation).order_by("name")
    )
    if not cohorts:
        raise click.ClickException(f"No cohorts in {organisation_slug}.")

    written = 0
    with_reason = 0
    for _ in range(pairs):
        for cohort in cohorts:
            # Flip away from the current state first, then back.
            steps = (
                (deactivate_cohort, reactivate_cohort)
                if cohort.is_active
                else (reactivate_cohort, deactivate_cohort)
            )
            for step in steps:
                written += 1
                reason = ""
                if written % reason_every == 0:
                    reason = REASONS[with_reason % len(REASONS)]
                    with_reason += 1
                step(cohort, actor=actor, reason=reason)

    visible = AuditLogEntry.unscoped.filter(organisation=organisation, run_id=None)
    click.echo(
        f"Wrote {written} entries ({with_reason} with a reason) as {actor_email} "
        f"on {', '.join(c.name for c in cohorts)}."
    )
    click.echo(
        f"{organisation_slug} now has {visible.count()} non-run entries, "
        f"{visible.exclude(reason='').count()} with a reason."
    )
    for cohort in cohorts:
        cohort.refresh_from_db()
        click.echo(f"{cohort.pk} {cohort.name}: is_active={cohort.is_active}")
