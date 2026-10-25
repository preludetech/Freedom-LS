"""Seed the browser-QA data set for educator-interface member administration.

Builds four organisations on the target site (Northside with Cohorts A, B, C
and the inactive Cohort Old; Southside with Cohort S; Westside with no
cohorts; Eastside with Cohort E and no members) and the educator personas of
the member-administration frontend QA plan: site admins, organisation admins
(one with an inactive OrganisationMember row), cohort admins and viewers
(one with no OrganisationMember row, one inactive user, one with a null
grantor, twelve filler viewers so Northside's members list pages), a learner
who is also a cohort admin, a learner with no role, a role-less user, and a
user on another Site.

Every persona's password is its own email address, with a verified primary
EmailAddress. Grants are made with the raw role utilities, granted by the
site's superuser (demodev@email.com on DemoDev) unless stated. Idempotent:
re-running reuses existing rows and restores any state a QA run changed on
them (names, active flags, grants, member rows).

Usage:
    uv run python manage.py qa_create_member_administration_scenario
    uv run python manage.py qa_create_member_administration_scenario --site-name DemoDev
"""

from __future__ import annotations

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import CohortMembershipFactory
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    OrganisationMember,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_organisation,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
    deactivate_object_role,
)

SUPERUSER_EMAIL = "demodev@email.com"
AWAY_SITE_NAME = "Bloom"
VIEWER_NUMBERS = (
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
)


def _ensure_user(
    site: Site, email: str, first: str, last: str, is_active: bool = True
) -> User:
    user: User | None = User._base_manager.filter(site=site, email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site,
                email=email,
                first_name=first,
                last_name=last,
                is_active=is_active,
            ),
        )
    else:
        user.first_name, user.last_name = first, last
        user.is_active = is_active
        user.set_password(email)
        user.save(update_fields=["first_name", "last_name", "is_active", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_learner_in_cohort(site: Site, cohort: Cohort, user: User) -> None:
    if not CohortMembership._base_manager.filter(
        cohort=cohort, learner__user=user
    ).exists():
        CohortMembershipFactory(site=site, cohort=cohort, learner__user=user)


def _set_member_state(user: User, org: Organisation, is_active: bool | None) -> None:
    """``None`` means the user must have no OrganisationMember row at all."""
    rows = OrganisationMember._base_manager.filter(user=user, organisation=org)
    if is_active is None:
        deleted = rows.delete()
        if deleted[0]:
            click.secho(
                f"Deleted OrganisationMember {user.email} / {org.slug}: {deleted}",
                fg="yellow",
            )
    else:
        rows.update(is_active=is_active)


def _clear_superuser(superuser: User) -> None:
    """The superuser holds no organisation role and no OrganisationMember rows."""
    org_ct = ContentType.objects.get_for_model(Organisation)
    for grant in ObjectRoleAssignment._base_manager.filter(
        user=superuser, content_type=org_ct, is_active=True
    ):
        org = Organisation._base_manager.get(pk=grant.object_id)
        click.secho(
            f"Removing {grant.role} on {org.slug} from {superuser.email}", fg="yellow"
        )
        deactivate_object_role(superuser, org, grant.role)
    deleted = OrganisationMember._base_manager.filter(user=superuser).delete()
    if deleted[0]:
        click.secho(
            f"Deleted {superuser.email} OrganisationMember rows: {deleted}",
            fg="yellow",
        )


def _seed(site: Site, away_site: Site) -> None:
    superuser: User | None = User._base_manager.filter(
        site=site, email=SUPERUSER_EMAIL, is_superuser=True
    ).first()
    if superuser is None:
        raise click.ClickException(
            f"Superuser {SUPERUSER_EMAIL} not found on {site.name}; "
            "run create_demo_data first."
        )

    north = _ensure_organisation(site, "Northside", "northside")
    south = _ensure_organisation(site, "Southside", "southside")
    west = _ensure_organisation(site, "Westside", "westside")
    east = _ensure_organisation(site, "Eastside", "eastside")

    cohort_a = _ensure_cohort(site, north, "Cohort A")
    cohort_b = _ensure_cohort(site, north, "Cohort B")
    cohort_c = _ensure_cohort(site, north, "Cohort C")
    cohort_old = _ensure_cohort(site, north, "Cohort Old", is_active=False)
    cohort_s = _ensure_cohort(site, south, "Cohort S")
    cohort_e = _ensure_cohort(site, east, "Cohort E")

    def grant(user: User, target: Organisation | Cohort, role: str) -> None:
        assign_object_role(user, target, role, assigned_by=superuser)

    site_admin = _ensure_user(site, "site.admin@qa.test", "Sandra", "Siteadmin")
    assign_site_role(site_admin, "site_admin", assigned_by=superuser, site=site)

    site_member = _ensure_user(site, "site.member@qa.test", "Sita", "Sitemember")
    assign_site_role(site_member, "site_admin", assigned_by=superuser, site=site)
    grant(site_member, cohort_a, "cohort_viewer")

    org_admin = _ensure_user(site, "org.admin@qa.test", "Oscar", "Orgadmin")
    grant(org_admin, north, "organisation_admin")
    org_admin2 = _ensure_user(site, "org.admin2@qa.test", "Olga", "Orgadmintwo")
    grant(org_admin2, north, "organisation_admin")

    lapsed = _ensure_user(site, "lapsed.admin@qa.test", "Lars", "Lapsed")
    grant(lapsed, north, "organisation_admin")
    _set_member_state(lapsed, north, is_active=False)

    cohort_admin = _ensure_user(site, "cohort.admin@qa.test", "Cora", "Cohortadmin")
    grant(cohort_admin, cohort_a, "cohort_admin")
    grant(cohort_admin, cohort_b, "cohort_admin")

    cohort_viewer = _ensure_user(site, "cohort.viewer@qa.test", "Vera", "Viewer")
    grant(cohort_viewer, cohort_a, "cohort_viewer")

    nomember = _ensure_user(site, "nomember@qa.test", "Noa", "Nomember")
    grant(nomember, cohort_b, "cohort_viewer")
    _set_member_state(nomember, north, is_active=None)

    off_viewer = _ensure_user(
        site, "off.viewer@qa.test", "Otto", "Off", is_active=False
    )
    grant(off_viewer, cohort_a, "cohort_viewer")

    both = _ensure_user(site, "both@qa.test", "Bea", "Both")
    grant(both, cohort_c, "cohort_admin")
    _ensure_learner_in_cohort(site, cohort_c, both)

    old_viewer = _ensure_user(site, "old.viewer@qa.test", "Ola", "Oldviewer")
    grant(old_viewer, cohort_a, "cohort_viewer")
    grant(old_viewer, cohort_old, "cohort_viewer")

    many = _ensure_user(site, "many.viewer@qa.test", "Manny", "Many")
    for cohort in (cohort_a, cohort_b, cohort_c, cohort_old):
        grant(many, cohort, "cohort_viewer")

    nameless = _ensure_user(site, "nameless.member@qa.test", "", "")
    grant(nameless, cohort_b, "cohort_viewer")

    nullgrant = _ensure_user(site, "nullgrant@qa.test", "Nia", "Nullgrant")
    assign_object_role(nullgrant, cohort_c, "cohort_viewer", assigned_by=None)

    for number, word in enumerate(VIEWER_NUMBERS, start=1):
        viewer = _ensure_user(site, f"viewer{number:02d}@qa.test", "Vee", word)
        grant(viewer, cohort_c, "cohort_viewer")

    existing = _ensure_user(site, "existing@qa.test", "Eve", "Existing")

    learner_only = _ensure_user(site, "learner.only@qa.test", "Lena", "Learner")
    _ensure_learner_in_cohort(site, cohort_a, learner_only)

    away = _ensure_user(away_site, "away@qa.test", "Avery", "Away")

    south_admin = _ensure_user(site, "south.admin@qa.test", "Sam", "South")
    grant(south_admin, south, "organisation_admin")
    west_admin = _ensure_user(site, "west.admin@qa.test", "Wes", "West")
    grant(west_admin, west, "organisation_admin")

    _clear_superuser(superuser)

    click.secho("--- Member administration QA data ---", fg="cyan", bold=True)
    click.echo(f"SITE {site.name} pk={site.pk}; away site {away_site.name}")
    for org in (north, south, west, east):
        members = list(
            OrganisationMember._base_manager.filter(organisation=org)
            .order_by("user__email")
            .values_list("user__email", "is_active")
        )
        click.echo(f"ORG {org.name!r} slug={org.slug} pk={org.pk} members={members}")
    for cohort in (cohort_a, cohort_b, cohort_c, cohort_old, cohort_s, cohort_e):
        click.echo(f"COHORT {cohort.name!r} pk={cohort.pk} active={cohort.is_active}")
    for user in (
        org_admin,
        org_admin2,
        cohort_viewer,
        south_admin,
        existing,
        away,
    ):
        click.echo(f"USER {user.email} pk={user.pk} site={user.site_id}")


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed (default: DemoDev).")
@click.option(
    "--away-site-name",
    default=AWAY_SITE_NAME,
    help=f"Other site for away@qa.test (default: {AWAY_SITE_NAME}).",
)
def command(site_name: str, away_site_name: str) -> None:
    """Seed organisations, cohorts and personas for member administration QA."""
    try:
        site = Site.objects.get(name=site_name)
        away_site = Site.objects.get(name=away_site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(str(e)) from e
    if away_site == site:
        raise click.ClickException("--away-site-name must differ from --site-name.")
    _pin_current_site(site)
    with _site_context(site):
        _seed(site, away_site)
