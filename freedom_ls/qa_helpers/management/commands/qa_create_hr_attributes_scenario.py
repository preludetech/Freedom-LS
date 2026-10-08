"""Seed two organisations, their HR lists and three learners for HR attributes QA.

Idempotent: re-running brings every record back to exactly the state below,
on the Site that ``demodev@email.com`` belongs to.

- ``QA Org One``: job titles Driver, Dispatcher, Fleet Manager (inactive);
  departments Operations, Finance; locations Cape Town, Durban.
- ``QA Org Two``: job title Driver; department Finance; no locations.
- Learners in QA Org One (password == email address):
  - ``qa_hr_held@email.com`` holds the inactive Fleet Manager, Operations,
    Cape Town and an organisation start date of 2019-03-01.
  - ``qa_hr_blank@email.com`` has no HR attributes row.
  - ``qa_hr_mover@email.com`` holds Driver only, with no dates.
- Neither organisation has an OrganisationHRSettings row.

Entries in either organisation outside the lists above are deleted. A
deletion blocked by another learner holding the entry is reported, not forced.

Usage:
    uv run python manage.py qa_create_hr_attributes_scenario
"""

from datetime import date
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.db import transaction
from django.db.models import ProtectedError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LearnerHRAttributesFactory,
    LocationFactory,
)
from freedom_ls.hr_attributes.models import (
    Department,
    JobTitle,
    LearnerHRAttributes,
    Location,
    OrganisationHRSettings,
)
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

ADMIN_EMAIL = "demodev@email.com"
ORG_ONE = "QA Org One"
ORG_TWO = "QA Org Two"

ListModel = type[JobTitle] | type[Department] | type[Location]
ListFactory = type[JobTitleFactory] | type[DepartmentFactory] | type[LocationFactory]
ListEntry = JobTitle | Department | Location

# (name, is_active) per organisation, per list.
JOB_TITLES = {
    ORG_ONE: [("Driver", True), ("Dispatcher", True), ("Fleet Manager", False)],
    ORG_TWO: [("Driver", True)],
}
DEPARTMENTS = {
    ORG_ONE: [("Operations", True), ("Finance", True)],
    ORG_TWO: [("Finance", True)],
}
LOCATIONS: dict[str, list[tuple[str, bool]]] = {
    ORG_ONE: [("Cape Town", True), ("Durban", True)],
    ORG_TWO: [],
}

LEARNERS = [
    ("qa_hr_held@email.com", "Hilda", "Held"),
    ("qa_hr_blank@email.com", "Bongani", "Blank"),
    ("qa_hr_mover@email.com", "Mpho", "Mover"),
]


def _ensure_organisation(site: Site, name: str) -> Organisation:
    organisation = Organisation._base_manager.filter(site=site, name=name).first()
    if organisation is None:
        organisation = cast(Organisation, OrganisationFactory(site=site, name=name))
        click.secho(f"Created organisation '{name}'", fg="green")
    return organisation


def _ensure_list(
    site: Site,
    organisation: Organisation,
    model: ListModel,
    factory_class: ListFactory,
    wanted: list[tuple[str, bool]],
) -> dict[str, ListEntry]:
    """Bring one organisation's list to exactly ``wanted``; return entries by name."""
    entries: dict[str, ListEntry] = {}
    for name, is_active in wanted:
        entry = model._base_manager.filter(
            site=site, organisation=organisation, name__iexact=name.strip()
        ).first()
        if entry is None:
            entry = cast(
                ListEntry,
                factory_class(
                    site=site,
                    organisation=organisation,
                    name=name,
                    is_active=is_active,
                ),
            )
        elif entry.name != name or entry.is_active != is_active:
            entry.name = name
            entry.is_active = is_active
            entry.save(update_fields=["name", "is_active"])
        entries[name] = entry

    extras = model._base_manager.filter(site=site, organisation=organisation).exclude(
        pk__in=[e.pk for e in entries.values()]
    )
    for extra in extras:
        label = f"{model.__name__} {extra.pk} '{extra.name}' in {organisation.name}"
        try:
            extra.delete()
            click.secho(f"Deleted extra {label}", fg="yellow")
        except ProtectedError:
            click.secho(f"Left {label}: another learner still holds it", fg="red")
    return entries


def _ensure_learner_user(site: Site, email: str, first: str, last: str) -> User:
    user = User._base_manager.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site, email=email, first_name=first, last_name=last, password=email
            ),
        )
        click.secho(f"Created user {email}", fg="green")
    else:
        user.first_name = first
        user.last_name = last
        user.is_active = True
        user.set_password(email)
        user.save()
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


@click.command()
def command() -> None:
    """Seed the HR attributes QA scenario on demodev@email.com's Site."""
    admin = User._base_manager.filter(email=ADMIN_EMAIL).first()
    if admin is None:
        raise click.ClickException(
            f"{ADMIN_EMAIL} not found. Run `uv run python manage.py "
            "create_demo_data --yes` first."
        )
    site = admin.site

    with transaction.atomic():
        org_one = _ensure_organisation(site, ORG_ONE)
        org_two = _ensure_organisation(site, ORG_TWO)
        organisations = {ORG_ONE: org_one, ORG_TWO: org_two}

        learners: dict[str, Learner] = {}
        for email, first, last in LEARNERS:
            user = _ensure_learner_user(site, email, first, last)
            learners[email] = cast(
                Learner,
                LearnerFactory(site=site, user=user, organisation=org_one),
            )

        # Drop the scenario learners' rows first so they never pin an entry
        # that the list reconciliation below needs to delete.
        LearnerHRAttributes._base_manager.filter(learner__in=learners.values()).delete()

        lists: dict[str, dict[str, dict[str, ListEntry]]] = {}
        for org_name, organisation in organisations.items():
            lists[org_name] = {
                "job_titles": _ensure_list(
                    site,
                    organisation,
                    JobTitle,
                    JobTitleFactory,
                    JOB_TITLES[org_name],
                ),
                "departments": _ensure_list(
                    site,
                    organisation,
                    Department,
                    DepartmentFactory,
                    DEPARTMENTS[org_name],
                ),
                "locations": _ensure_list(
                    site, organisation, Location, LocationFactory, LOCATIONS[org_name]
                ),
            }

        one = lists[ORG_ONE]
        LearnerHRAttributesFactory(
            site=site,
            learner=learners["qa_hr_held@email.com"],
            job_title=one["job_titles"]["Fleet Manager"],
            department=one["departments"]["Operations"],
            location=one["locations"]["Cape Town"],
            organisation_start_date=date(2019, 3, 1),
        )
        LearnerHRAttributesFactory(
            site=site,
            learner=learners["qa_hr_mover@email.com"],
            job_title=one["job_titles"]["Driver"],
            department=None,
            location=None,
        )

        deleted = OrganisationHRSettings._base_manager.filter(
            organisation__in=organisations.values()
        ).delete()
        click.secho(f"OrganisationHRSettings deleted: {deleted}", fg="yellow")

        if not Cohort._base_manager.filter(site=site).exists():
            CohortFactory(site=site, organisation=org_one, name="QA HR Cohort")
            click.secho("Created cohort 'QA HR Cohort'", fg="green")

    click.secho(f"\nSite: {site.name} ({site.domain})", bold=True)
    for org_name, organisation in organisations.items():
        click.secho(f"{org_name}: {organisation.pk}", bold=True)
        for list_name, entries in lists[org_name].items():
            for entry in entries.values():
                click.echo(f"  {list_name}: {entry} -> {entry.pk}")
    for email, learner in learners.items():
        click.echo(
            f"Learner {email}: learner pk {learner.pk}, user pk {learner.user_id}"
        )
