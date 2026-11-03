"""Seed audit log history for the educator History tabs and the organisation Audit log.

Writes through the real services where they exist (add_to_cohort,
move_between_cohorts, remove_from_cohort, deactivate_learner,
reactivate_learner) and through the audit writer for the rest (a setup email
resend, and a bulk run of per-object entries plus its summary).

Builds, in one organisation:
- "Audit QA Cohort" and "Audit QA Cohort B"
- learner Amara Okafor with 5 history entries (description, reason, neither,
  and a system reactivation)
- 56 bulk learners added to Audit QA Cohort in one bulk run with a reason,
  so the audit log row lists 50 entries and "and 6 more"
- two more cohort members, one later removed
- an entry by "Gone Person", whose user is then deleted

Audit entries are append-only, so this refuses to run twice: it stops when
"Audit QA Cohort" already exists in the organisation.

Usage:
    uv run python manage.py qa_create_audit_log_history
    uv run python manage.py qa_create_audit_log_history --organisation-slug demodev
"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import djclick as click
from allauth.account.models import EmailAddress

from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.writer import record_entry, record_run_summary
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.learner_actions import (
    _add_membership,
    add_to_cohort,
    deactivate_learner,
    move_between_cohorts,
    reactivate_learner,
    record_learner_entry,
    remove_from_cohort,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.models import Organisation

PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
COHORT_NAME = "Audit QA Cohort"
OTHER_COHORT_NAME = "Audit QA Cohort B"
BULK_COUNT = 56
BULK_REASON = "Spring intake enrolment from the registrar's list"
DEACTIVATION_REASON = "Left the programme after the March intake"


def _user(organisation: Organisation, email: str, first: str, last: str) -> User:
    user = cast(
        User,
        UserFactory(
            site=organisation.site,
            email=email,
            first_name=first,
            last_name=last,
            password=PASSWORD,
        ),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def _learner(organisation: Organisation, email: str, first: str, last: str) -> Learner:
    return ensure_learner(_user(organisation, email, first, last), organisation)


def _record_run_entry(
    learner: Learner, cohort: Cohort, actor: User, run_id: UUID
) -> None:
    """One per-object entry of the bulk run."""
    record_entry(
        action="cohort_membership.added",
        actor=actor,
        target=learner,
        target_label=learner.user.display_name,
        organisation=learner.organisation,
        subjects=[cohort],
        details={"cohort": cohort.name},
        run_id=run_id,
    )


@click.command()
@click.option("--organisation-slug", default="demodev", show_default=True)
@click.option("--admin-email", default="demodev@email.com", show_default=True)
def command(organisation_slug: str, admin_email: str) -> None:
    organisation = Organisation._base_manager.get(slug=organisation_slug)
    site = organisation.site
    if Cohort._base_manager.filter(
        organisation=organisation, name=COHORT_NAME
    ).exists():
        raise click.ClickException(
            f"{COHORT_NAME!r} already exists in {organisation_slug}; audit entries "
            "are append-only, so this command does not run twice."
        )
    admin = User._base_manager.get(email=admin_email, site=site)

    with transaction.atomic():
        educator = _user(organisation, "audit.priya@email.com", "Priya", "Naidoo")
        cohort = cast(
            Cohort,
            CohortFactory(site=site, organisation=organisation, name=COHORT_NAME),
        )
        other = cast(
            Cohort,
            CohortFactory(site=site, organisation=organisation, name=OTHER_COHORT_NAME),
        )

        # The learner: description, neither, move, reason, system.
        amara = _learner(organisation, "audit.amara@email.com", "Amara", "Okafor")
        add_to_cohort(amara, cohort, actor=admin)
        record_learner_entry(amara, "learner.setup_email_resent", admin)
        move_between_cohorts(amara, cohort, other, actor=educator)
        deactivate_learner(amara, actor=educator, reason=DEACTIVATION_REASON)
        reactivate_learner(amara, actor=None)

        # Two more members by hand, one later removed.
        tomas = _learner(organisation, "audit.tomas@email.com", "Tomas", "Berg")
        lina = _learner(organisation, "audit.lina@email.com", "Lina", "Haddad")
        add_to_cohort(tomas, cohort, actor=educator)
        add_to_cohort(lina, cohort, actor=admin)
        remove_from_cohort(lina, cohort, actor=admin, reason="Enrolled in error")

        # An actor whose account is later deleted.
        gone = _user(organisation, "audit.gone@email.com", "Gone", "Person")
        kofi = _learner(organisation, "audit.kofi@email.com", "Kofi", "Mensah")
        add_to_cohort(kofi, cohort, actor=gone)

        # One bulk run: per-object entries sharing a run_id, then the summary.
        run_id = uuid4()
        for n in range(1, BULK_COUNT + 1):
            learner = _learner(
                organisation, f"audit.bulk{n:02d}@email.com", "Bulk", f"Learner {n:02d}"
            )
            _add_membership(learner, cohort)
            _record_run_entry(learner, cohort, admin, run_id)
        record_run_summary(
            action="bulk_action.completed",
            run_id=run_id,
            organisation=organisation,
            actor=admin,
            counts={"changed": BULK_COUNT, "skipped": 0, "failed": 0},
            reason=BULK_REASON,
            bulk_action="cohort_membership.added",
        )

    deleted = gone.delete()
    click.echo(f"Deleted Gone Person's user: {deleted}")
    click.echo(f"Learner Amara Okafor pk={amara.pk}")
    click.echo(
        f"Cohort {COHORT_NAME} pk={cohort.pk}; {OTHER_COHORT_NAME} pk={other.pk}"
    )
    click.echo(f"Bulk run_id={run_id}")
