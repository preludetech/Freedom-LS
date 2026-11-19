"""Seed the cross-organisation course-scope personas on Harbour College and Northwind.

Run ``content_save demo_content <site>`` first: it creates the Harbour College
and Northwind Logistics organisations and their demo courses. This builds,
idempotently:

* qa_harbour_educator@email.com: organisation_admin on Harbour College.
* qa_northwind_educator@email.com: organisation_admin on Northwind Logistics.
* "QA Harbour Cohort" in Harbour College, with qa_harbour_learner@email.com.
* qa_harbour_solo@email.com: a Harbour College learner in no cohort.

Every persona's password is its own email address, with a verified primary
EmailAddress and the site's terms and privacy consents. The command creates
and never deletes: clearing stray registrations is left to the caller.

Usage:
    uv run python manage.py qa_create_org_course_scope_scenario
    uv run python manage.py qa_create_org_course_scope_scenario --site-name DemoDev
"""

from __future__ import annotations

import djclick as click

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.learner_actions import add_to_cohort
from freedom_ls.learner_management.models import CohortMembership
from freedom_ls.learner_management.utils import ensure_learner, ensure_staff_member
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_user,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_single_org_educator import (
    _ensure_consents,
)
from freedom_ls.role_based_permissions.utils import assign_object_role

HARBOUR_SLUG = "harbour-college"
NORTHWIND_SLUG = "northwind-logistics"
HARBOUR_EDUCATOR = "qa_harbour_educator@email.com"
NORTHWIND_EDUCATOR = "qa_northwind_educator@email.com"
HARBOUR_LEARNER = "qa_harbour_learner@email.com"
HARBOUR_SOLO = "qa_harbour_solo@email.com"
COHORT_NAME = "QA Harbour Cohort"
ORG_ADMIN = "organisation_admin"
# Demo course uuids, from demo_content/functionality_demo_organisation_course_*.
DEMO_COURSES = {
    "northwind (shared with Harbour)": "26c2e0d5-534f-40dc-86de-8218355233e5",
    "northwind unshared": "c358d156-4f88-4ea7-ac1a-538ee8a47152",
    "harbour": "1eb2b2d6-7b7f-4c0e-9660-7893b1054b03",
}


def _organisation(site: Site, slug: str) -> Organisation:
    org: Organisation | None = Organisation._base_manager.filter(
        site=site, slug=slug
    ).first()
    if org is None:
        raise click.ClickException(
            f"Organisation {slug!r} not found on {site.name}; run "
            f"`content_save demo_content {site.name}` first."
        )
    return org


def _login_ready_user(site: Site, email: str) -> User:
    """Password = email, verified primary EmailAddress, terms and privacy consents."""
    user = _ensure_user(site, email)
    user.set_password(email)
    user.save(update_fields=["password"])
    _ensure_consents(site, user)
    return user


def _educator(site: Site, email: str, org: Organisation) -> User:
    user = _login_ready_user(site, email)
    ensure_staff_member(user, org)
    assign_object_role(user, org, ORG_ADMIN)
    return user


@click.command()
@click.option("--site-name", default="DemoDev", show_default=True)
def command(site_name: str) -> None:
    site = Site.objects.get(name=site_name)
    harbour = _organisation(site, HARBOUR_SLUG)
    northwind = _organisation(site, NORTHWIND_SLUG)
    _pin_current_site(site)
    with _site_context(site), transaction.atomic():
        harbour_educator = _educator(site, HARBOUR_EDUCATOR, harbour)
        northwind_educator = _educator(site, NORTHWIND_EDUCATOR, northwind)
        cohort = _ensure_cohort(site, harbour, COHORT_NAME)
        learner_user = _login_ready_user(site, HARBOUR_LEARNER)
        learner = ensure_learner(learner_user, harbour)
        if not CohortMembership._base_manager.filter(
            cohort=cohort, learner=learner
        ).exists():
            add_to_cohort(learner, cohort, actor=harbour_educator)
        solo_user = _login_ready_user(site, HARBOUR_SOLO)
        solo = ensure_learner(solo_user, harbour)

    click.echo(f"Site: {site.name} (pk {site.pk})")
    for label, user, org in (
        ("Harbour educator", harbour_educator, harbour),
        ("Northwind educator", northwind_educator, northwind),
    ):
        click.echo(
            f"{label}: {user.email} / {user.email} (user pk {user.pk}), "
            f"{ORG_ADMIN} on {org.slug} (org pk {org.pk})"
        )
    click.echo(f"Cohort: {cohort.name} (pk {cohort.pk}) in {harbour.slug}")
    click.echo(
        f"Cohort learner: {learner_user.email} / {learner_user.email} "
        f"(user pk {learner_user.pk}, learner pk {learner.pk})"
    )
    click.echo(
        f"Solo learner: {solo_user.email} / {solo_user.email} "
        f"(user pk {solo_user.pk}, learner pk {solo.pk})"
    )
    for label, uuid in DEMO_COURSES.items():
        course = Course._base_manager.filter(site=site, pk=uuid).first()
        click.echo(
            f"Course {label}: {course.pk} {course.slug!r}"
            if course
            else f"Course {label}: {uuid} MISSING on {site.name}"
        )
