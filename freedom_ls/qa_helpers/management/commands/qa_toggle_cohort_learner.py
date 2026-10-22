"""Remove a learner from a cohort and deactivate them, or put them back.

``remove`` takes the learner out of the cohort and sets their organisation
``Learner`` row inactive; ``restore`` adds them back and reactivates the row.
Both go through ``learner_actions`` (the same services the educator
interface's Remove / Deactivate / Reactivate / Add to cohort actions call), so
the webhook events and model signals fire exactly as they do from the UI.

Removing a membership drops no course registration: ``CohortCourseRegistration``
belongs to the cohort, not the member, so the learner regains the cohort's
courses as soon as the membership is back. Course progress records are kept
either way.

Idempotent: each step reports "already" when there is nothing to change.

Usage:
    uv run python manage.py qa_toggle_cohort_learner remove \
        --learner-email l3@qa.test --cohort-name "Cohort A"
    uv run python manage.py qa_toggle_cohort_learner restore \
        --learner-email l3@qa.test --cohort-name "Cohort A"
"""

from __future__ import annotations

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.learner_management.learner_actions import (
    add_to_cohort,
    deactivate_learner,
    reactivate_learner,
    remove_from_cohort,
)
from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _not_found(description: str) -> click.ClickException:
    return click.ClickException(f"{description} not found.")


def _report(learner: Learner, cohort: Cohort) -> None:
    learner.refresh_from_db(fields=["is_active"])
    member = CohortMembership._base_manager.filter(
        learner=learner, cohort=cohort
    ).exists()
    registrations = list(
        cohort.course_registrations.filter(is_active=True).values_list(
            "course__slug", flat=True
        )
    )
    click.secho(
        f"Now: Learner.is_active={learner.is_active}, "
        f"member of '{cohort.name}'={member}, "
        f"cohort's active course registrations={registrations}",
        fg="cyan",
    )


@click.command()
@click.argument("action", type=click.Choice(["remove", "restore"]))
@click.option("--learner-email", required=True, help="The learner's email address.")
@click.option("--cohort-name", required=True, help="Name of the cohort.")
@click.option(
    "--organisation-slug",
    default="northside",
    show_default=True,
    help="Slug of the organisation the learner and cohort belong to.",
)
@click.option("--site-name", default="DemoDev", show_default=True)
def command(
    action: str,
    learner_email: str,
    cohort_name: str,
    organisation_slug: str,
    site_name: str,
) -> None:
    """Remove a learner from a cohort and deactivate them, or restore both."""
    site = _get_site(site_name)
    organisation = Organisation._base_manager.filter(
        site=site, slug=organisation_slug
    ).first()
    if organisation is None:
        raise _not_found(f"Organisation '{organisation_slug}' on {site.name}")
    learner = (
        Learner._base_manager.filter(
            site=site, organisation=organisation, user__email=learner_email
        )
        .select_related("user", "site")
        .first()
    )
    if learner is None:
        raise _not_found(f"Learner '{learner_email}' in {organisation.name}")
    cohort = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=cohort_name
    ).first()
    if cohort is None:
        raise _not_found(f"Cohort '{cohort_name}' in {organisation.name}")
    click.secho(
        f"{action}: {learner_email} (Learner {learner.pk}) / "
        f"'{cohort.name}' (Cohort {cohort.pk}) on {site.name}/{organisation.slug}",
        fg="cyan",
        bold=True,
    )

    _pin_current_site(site)
    with _site_context(site):
        if action == "remove":
            removed = remove_from_cohort(learner, cohort)
            click.echo(
                "Removed from cohort." if removed else "Already not in the cohort."
            )
            changed = deactivate_learner(learner)
            click.echo("Learner deactivated." if changed else "Already inactive.")
        else:
            changed = reactivate_learner(learner)
            click.echo("Learner reactivated." if changed else "Already active.")
            added = add_to_cohort(learner, cohort)
            click.echo("Added to cohort." if added else "Already in the cohort.")

    _report(learner, cohort)
