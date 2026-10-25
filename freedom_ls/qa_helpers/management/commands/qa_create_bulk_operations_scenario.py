"""Seed (and reset) the browser-QA data set for educator-interface bulk operations.

Builds spec_dd/.../educator-interface-8-bulk-operations/3. frontend_qa.md §0.2:
Course Pub / Hid, organisations Northside and Southside beside the site's
default organisation, Cohorts A / B / C / Old / S, the 60 cohort-less bulk
learners, the pending, removed, solo and other-site learners, and the educator
personas.

Every persona except pending@qa.test has its own email address as password and
a verified primary EmailAddress; pending@qa.test is made the way
`match_or_create_user` makes one (unusable password, never logged in).

Idempotent, and a reset: before seeding it deletes every learner import and
bulk action run of Northside and Southside, every @qa.test user the scenario
does not list (import01..26, dup, semi1/2, big*, ...), and every membership,
learner row, individual registration, cohort registration, organisation
member and object role of a listed user or cohort that the scenario does not
list. Listed rows are then put back to their listed state.

Usage:
    uv run python manage.py qa_create_bulk_operations_scenario
    uv run python manage.py qa_create_bulk_operations_scenario --site-name DemoDev
"""

from __future__ import annotations

from collections import Counter

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import Model, QuerySet

from freedom_ls.accounts.account_setup import match_or_create_user
from freedom_ls.accounts.models import SiteSignupPolicy, User
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.learner_management.learner_actions import deactivate_learner
from freedom_ls.learner_management.models import (
    BulkActionRun,
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    LearnerImport,
    OrganisationMember,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_cohort_registration,
    _ensure_member,
    _ensure_organisation,
)
from freedom_ls.qa_helpers.management.commands.qa_create_learner_administration_scenario import (
    _ensure_course,
    _ensure_individual_registration,
    _ensure_user,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import assign_object_role

QA_DOMAIN = "@qa.test"
NORTH = "northside"
SOUTH = "southside"

# Cohort name -> (organisation slug, is_active, registered course titles, member emails).
COHORTS: dict[str, tuple[str, bool, tuple[str, ...], tuple[str, ...]]] = {
    "Cohort A": (
        NORTH,
        True,
        ("Course Pub",),
        ("ada@qa.test", "pending@qa.test", "removed@qa.test"),
    ),
    "Cohort B": (
        NORTH,
        True,
        ("Course Pub", "Course Hid"),
        ("ben@qa.test", "bea@qa.test"),
    ),
    "Cohort C": (NORTH, True, (), ()),
    "Cohort Old": (NORTH, False, (), ("old@qa.test",)),
    "Cohort S": (SOUTH, True, (), ("south@qa.test",)),
}

BULK_EMAILS = tuple(f"bulk{n:02d}@qa.test" for n in range(1, 61))

# Learners on the scenario site: email -> (first name, last name, org slug).
LEARNERS: dict[str, tuple[str, str, str]] = {
    "ada@qa.test": ("Ada", "Lovelace", NORTH),
    "pending@qa.test": ("Pending", "Person", NORTH),
    "ben@qa.test": ("Ben", "Brown", NORTH),
    "bea@qa.test": ("Bea", "Blue", NORTH),
    "old@qa.test": ("Olga", "Old", NORTH),
    "removed@qa.test": ("Rae", "Removed", NORTH),
    "solo@qa.test": ("Sol", "Solo", NORTH),
    "south@qa.test": ("Sam", "South", SOUTH),
    **{
        email: (f"Bulk {n:02d}", "Alpha" if n <= 30 else "Beta", NORTH)
        for n, email in enumerate(BULK_EMAILS, start=1)
    },
}

# Persona email -> (first name, last name, role, target kind, target names).
PERSONAS: dict[str, tuple[str, str, str, str, tuple[str, ...]]] = {
    "org.admin@qa.test": ("Orla", "Admin", "organisation_admin", "org", (NORTH,)),
    "cohort.admin@qa.test": (
        "Cole",
        "Admin",
        "cohort_admin",
        "cohort",
        ("Cohort A", "Cohort B"),
    ),
    "cohort.viewer@qa.test": (
        "Vera",
        "Viewer",
        "cohort_viewer",
        "cohort",
        ("Cohort A",),
    ),
    "south.admin@qa.test": ("Sid", "Admin", "organisation_admin", "org", (SOUTH,)),
}

AWAY_EMAIL = "away@qa.test"
SOLO_EMAIL = "solo@qa.test"
REMOVED_EMAIL = "removed@qa.test"
PENDING_EMAIL = "pending@qa.test"


def _other_site(site: Site) -> Site:
    other = Site.objects.exclude(pk=site.pk).order_by("name").first()
    if other is None:
        raise click.ClickException(f"No Site other than {site.name} for {AWAY_EMAIL}.")
    return other


def _delete(label: str, qs: QuerySet[Model], counts: Counter[str]) -> None:
    """Print what goes, delete it, and add the cascade counts to `counts`."""
    rows = list(qs)
    if not rows:
        return
    for row in rows:
        click.echo(f"DELETE {label} pk={row.pk} {row}")
    _, per_model = qs.delete()
    counts.update(per_model)


def _purge_stale(
    site: Site, orgs: dict[str, Organisation], cohorts: dict[str, Cohort]
) -> Counter[str]:
    """Delete every QA row in scope that §0.2 does not list. Returns the cascade counts."""
    counts: Counter[str] = Counter()
    away_site = _other_site(site)
    org_ids = [o.pk for o in orgs.values()]

    _delete(
        "LearnerImport",
        LearnerImport._base_manager.filter(organisation_id__in=org_ids),
        counts,
    )
    _delete(
        "BulkActionRun",
        BulkActionRun._base_manager.filter(organisation_id__in=org_ids),
        counts,
    )

    site_emails = set(LEARNERS) | set(PERSONAS)
    qa_users = User._base_manager.filter(email__iendswith=QA_DOMAIN)
    stale_ids = [
        u.pk
        for u in qa_users
        if not (
            (u.email in site_emails and u.site_id == site.pk)
            or (u.email == AWAY_EMAIL and u.site_id == away_site.pk)
        )
    ]
    _delete("User", User._base_manager.filter(pk__in=stale_ids), counts)

    expected_learners = {(e, orgs[org].pk) for e, (_, _, org) in LEARNERS.items()}
    stale_learners = [
        lr.pk
        for lr in Learner._base_manager.filter(user__email__iendswith=QA_DOMAIN)
        if (lr.user.email, lr.organisation_id) not in expected_learners
    ]
    _delete("Learner", Learner._base_manager.filter(pk__in=stale_learners), counts)

    expected_members = {
        (email, cohorts[name].pk)
        for name, (_, _, _, members) in COHORTS.items()
        for email in members
    }
    cohort_ids = [c.pk for c in cohorts.values()]
    memberships = CohortMembership._base_manager.filter(
        cohort_id__in=cohort_ids
    ) | CohortMembership._base_manager.filter(learner__user__email__iendswith=QA_DOMAIN)
    stale_members = [
        m.pk
        for m in memberships.select_related("learner__user")
        if (m.learner.user.email, m.cohort_id) not in expected_members
    ]
    _delete(
        "CohortMembership",
        CohortMembership._base_manager.filter(pk__in=stale_members),
        counts,
    )

    expected_regs = {
        (cohorts[name].pk, title)
        for name, (_, _, titles, _) in COHORTS.items()
        for title in titles
    }
    stale_regs = [
        r.pk
        for r in CohortCourseRegistration._base_manager.filter(
            cohort_id__in=cohort_ids
        ).select_related("course")
        if (r.cohort_id, r.course.title) not in expected_regs
    ]
    _delete(
        "CohortCourseRegistration",
        CohortCourseRegistration._base_manager.filter(pk__in=stale_regs),
        counts,
    )

    _delete(
        "LearnerCourseRegistration",
        LearnerCourseRegistration._base_manager.filter(
            learner__user__email__iendswith=QA_DOMAIN
        ).exclude(learner__user__email=SOLO_EMAIL, course__title="Course Pub"),
        counts,
    )

    org_ct = ContentType.objects.get_for_model(Organisation)
    cohort_ct = ContentType.objects.get_for_model(Cohort)
    expected_roles: set[tuple[str, int, str, str]] = set()
    expected_org_members: set[tuple[str, object]] = set()
    for email, (_, _, role, kind, names) in PERSONAS.items():
        for name in names:
            if kind == "org":
                target: Model = orgs[name]
                ct = org_ct
                expected_org_members.add((email, orgs[name].pk))
            else:
                target = cohorts[name]
                ct = cohort_ct
                expected_org_members.add((email, cohorts[name].organisation_id))
            expected_roles.add((email, ct.pk, str(target.pk), role))
    stale_roles = [
        a.pk
        for a in ObjectRoleAssignment._base_manager.filter(
            user__email__iendswith=QA_DOMAIN
        ).select_related("user")
        if (a.user.email, a.content_type_id, a.object_id, a.role) not in expected_roles
    ]
    _delete(
        "ObjectRoleAssignment",
        ObjectRoleAssignment._base_manager.filter(pk__in=stale_roles),
        counts,
    )
    stale_org_members = [
        m.pk
        for m in OrganisationMember._base_manager.filter(
            user__email__iendswith=QA_DOMAIN
        ).select_related("user")
        if (m.user.email, m.organisation_id) not in expected_org_members
    ]
    _delete(
        "OrganisationMember",
        OrganisationMember._base_manager.filter(pk__in=stale_org_members),
        counts,
    )
    return counts


def _ensure_pending(site: Site, first_name: str, last_name: str) -> User:
    """A never-logged-in user with an unusable password, as an import makes one."""
    user, created = match_or_create_user(site, PENDING_EMAIL, first_name, last_name)
    if not created:
        user.set_unusable_password()
        user.last_login = None
        user.is_active = True
        user.first_name = first_name
        user.last_name = last_name
        user.save(
            update_fields=[
                "password",
                "last_login",
                "is_active",
                "first_name",
                "last_name",
            ]
        )
        EmailAddress.objects.update_or_create(
            user=user, email=PENDING_EMAIL, defaults={"verified": True, "primary": True}
        )
    return user


def _seed(site: Site) -> None:
    courses = {
        "Course Pub": _ensure_course(
            site, "Course Pub", CourseVisibility.PUBLISHED, topics=3
        ),
        "Course Hid": _ensure_course(
            site, "Course Hid", CourseVisibility.HIDDEN, topics=1
        ),
    }
    orgs = {
        NORTH: _ensure_organisation(site, "Northside", NORTH),
        SOUTH: _ensure_organisation(site, "Southside", SOUTH),
    }
    for org in orgs.values():
        if org.is_default:
            raise click.ClickException(
                f"{org.slug} is the site's default organisation."
            )
    cohorts = {
        name: _ensure_cohort(site, orgs[org], name, is_active=active)
        for name, (org, active, _, _) in COHORTS.items()
    }

    counts = _purge_stale(site, orgs, cohorts)
    click.echo(f"Deleted (cascade counts): {dict(counts) or 'nothing'}")

    users: dict[str, User] = {}
    for email, (first, last, _) in LEARNERS.items():
        if email == PENDING_EMAIL:
            users[email] = _ensure_pending(site, first, last)
        else:
            users[email] = _ensure_user(site, email, first, last)
    _ensure_user(_other_site(site), AWAY_EMAIL, "Avery", "Away")

    for name, (_, _, titles, members) in COHORTS.items():
        cohort = cohorts[name]
        for title in titles:
            _ensure_cohort_registration(site, cohort, courses[title])
        for email in members:
            _ensure_member(site, cohort, users[email])

    # Every listed learner row active (an import or bulk action may have
    # deactivated one) except the removed learner, who is deactivated. Never
    # flipping the removed row to active first keeps a re-run free of a
    # learner.deactivated webhook event.
    for email, (_, _, org_slug) in LEARNERS.items():
        if email != REMOVED_EMAIL:
            ensure_learner(users[email], orgs[org_slug])
    deactivate_learner(
        Learner._base_manager.get(user=users[REMOVED_EMAIL], organisation=orgs[NORTH])
    )
    _ensure_individual_registration(
        site,
        Learner._base_manager.get(user=users[SOLO_EMAIL], organisation=orgs[NORTH]),
        courses["Course Pub"],
    )

    for email, (first, last, role, kind, names) in PERSONAS.items():
        persona = _ensure_user(site, email, first, last)
        for name in names:
            assign_object_role(
                persona, orgs[name] if kind == "org" else cohorts[name], role
            )

    policy: SiteSignupPolicy | None = SiteSignupPolicy.objects.filter(site=site).first()
    if policy is not None and policy.additional_registration_forms:
        click.secho(
            f"Cleared SiteSignupPolicy.additional_registration_forms "
            f"{policy.additional_registration_forms}",
            fg="yellow",
        )
        policy.additional_registration_forms = []
        policy.save(update_fields=["additional_registration_forms"])

    _report(site, list(courses.values()), list(orgs.values()), list(cohorts.values()))


def _report(
    site: Site, courses: list[Course], orgs: list[Organisation], cohorts: list[Cohort]
) -> None:
    click.secho("--- Bulk operations QA data ---", fg="cyan", bold=True)
    for c in courses:
        click.echo(f"COURSE {c.title!r} pk={c.pk} visibility={c.visibility}")
    for o in orgs:
        click.echo(f"ORG {o.name!r} pk={o.pk} slug={o.slug} default={o.is_default}")
    for cohort in cohorts:
        cohort.refresh_from_db()
        members = CohortMembership._base_manager.filter(cohort=cohort)
        regs = CohortCourseRegistration._base_manager.filter(cohort=cohort)
        click.echo(
            f"COHORT {cohort.name!r} pk={cohort.pk} active={cohort.is_active} "
            f"members={sorted(members.values_list('learner__user__email', flat=True))} "
            f"courses={sorted(regs.values_list('course__title', flat=True))}"
        )
    learners = Learner._base_manager.filter(user__email__iendswith=QA_DOMAIN)
    click.echo(
        f"LEARNERS total={learners.count()} active={learners.filter(is_active=True).count()} "
        f"inactive={sorted(learners.filter(is_active=False).values_list('user__email', flat=True))}"
    )
    click.echo(
        f"QA USERS on {site.name}: "
        f"{User._base_manager.filter(site=site, email__iendswith=QA_DOMAIN).count()}"
    )
    away = User._base_manager.select_related("site").get(email=AWAY_EMAIL)
    click.echo(f"AWAY {away.email} pk={away.pk} site={away.site.name}")
    click.echo(
        f"IMPORTS={LearnerImport._base_manager.filter(organisation__in=orgs).count()} "
        f"BULK_RUNS={BulkActionRun._base_manager.filter(organisation__in=orgs).count()}"
    )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed (default: DemoDev).")
def command(site_name: str) -> None:
    """Seed, or reset to, the educator-interface bulk operations QA scenario."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site '{site_name}' not found.") from e
    _pin_current_site(site)
    with _site_context(site):
        _seed(site)
