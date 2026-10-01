"""Seed the browser-QA data set for the educator-interface permissions pass.

Covers ``spec_dd/2. in progress/educator-interface-5-permissions/3. frontend_qa.md``
§0.2: organisations Northside (Cohort A, Cohort B, Cohort Empty) and Southside
(Cohort S), five learners, seven role personas granted through the raw role
utilities, and one ready GeneratedReport each for Cohort A and Cohort B.

Every persona's password is its own email address. Idempotent: re-running
restores the documented shape (grants re-activated, member rows reset,
stale QA cohorts from earlier runs removed, a renamed Cohort A renamed back).

Usage:
    uv run python manage.py qa_create_permissions_scenario
"""

from __future__ import annotations

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    OrganisationMember,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _clear_registration_gate,
    _ensure_organisation,
    _get_course,
    _pin_current_site,
    _site_context,
)
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.tasks import generate_cohort_report
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
)

COURSE_SLUG = "functionality-demo-course-parts"
NORTHSIDE = ("Northside", "northside")
SOUTHSIDE = ("Southside", "southside")
COHORT_A, COHORT_B, COHORT_EMPTY, COHORT_S = (
    "Cohort A",
    "Cohort B",
    "Cohort Empty",
    "Cohort S",
)
# Leftovers from earlier QA runs that would contradict this shape.
STALE_COHORT_NAMES = ["QA Cohort 1", "QA Cohort Site", "Too Late", "Sneaky"]
RENAMED_COHORT_A = "Cohort A (renamed)"


def _ensure_cohort(site: Site, organisation: Organisation, name: str) -> Cohort:
    cohort: Cohort | None = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=name
    ).first()
    if cohort is not None:
        return cohort
    return cast(Cohort, CohortFactory(site=site, organisation=organisation, name=name))


def _ensure_user(site: Site, email: str, first: str, last: str) -> User:
    """Login-ready persona, password = email, verified primary address."""
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name=first,
                last_name=last,
                password=email,
                site=site,
            ),
        )
    else:
        user.first_name, user.last_name = first, last
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(email)
        user.save()
        user.user_permissions.clear()
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _set_member(user: User, organisation: Organisation, active: bool) -> None:
    OrganisationMember._base_manager.update_or_create(
        site=organisation.site,
        user=user,
        organisation=organisation,
        defaults={"is_active": active},
    )


def _ensure_membership(site: Site, cohort: Cohort, user: User) -> None:
    learner = ensure_learner(user, cohort.organisation)
    if not CohortMembership._base_manager.filter(
        cohort=cohort, learner=learner
    ).exists():
        CohortMembershipFactory(site=site, cohort=cohort, learner=learner)


def _ensure_cohort_registration(site: Site, cohort: Cohort, course: Course) -> None:
    CohortCourseRegistration._base_manager.filter(cohort=cohort, course=course).update(
        is_active=True
    )
    if not CohortCourseRegistration._base_manager.filter(
        cohort=cohort, course=course
    ).exists():
        CohortCourseRegistrationFactory(site=site, cohort=cohort, course=course)


def _ensure_user_registration(
    site: Site, organisation: Organisation, user: User, course: Course
) -> None:
    learner = ensure_learner(user, organisation)
    LearnerCourseRegistration._base_manager.filter(
        learner=learner, course=course
    ).update(is_active=True)
    if not LearnerCourseRegistration._base_manager.filter(
        learner=learner, course=course
    ).exists():
        LearnerCourseRegistrationFactory(site=site, learner=learner, course=course)


def _ensure_ready_report(
    site: Site, cohort: Cohort, requested_by: User
) -> GeneratedReport:
    existing: GeneratedReport | None = GeneratedReport._base_manager.filter(
        site=site, cohort=cohort, status=GeneratedReport.STATUS_READY
    ).first()
    if existing is not None:
        return existing
    report = cast(
        GeneratedReport,
        GeneratedReportFactory(site=site, cohort=cohort, requested_by=requested_by),
    )
    generate_cohort_report(str(report.pk), site.pk)
    report.refresh_from_db()
    return report


def _cleanup(site: Site, northside: Organisation) -> list[str]:
    notes: list[str] = []
    renamed = Cohort._base_manager.filter(
        site=site, organisation=northside, name=RENAMED_COHORT_A
    ).first()
    if renamed is not None:
        if Cohort._base_manager.filter(
            site=site, organisation=northside, name=COHORT_A
        ).exists():
            renamed.delete()
            notes.append(f"deleted duplicate {RENAMED_COHORT_A!r}")
        else:
            renamed.name = COHORT_A
            renamed.save(update_fields=["name"])
            notes.append(f"renamed {RENAMED_COHORT_A!r} back to {COHORT_A!r}")
    stale = Cohort._base_manager.filter(site=site, name__in=STALE_COHORT_NAMES)
    for cohort in stale:
        notes.append(
            f"deleted stale cohort {cohort.pk} {cohort.name!r}: {cohort.delete()}"
        )
    return notes


def _seed(site: Site) -> None:
    course = _get_course(site, COURSE_SLUG)
    northside = _ensure_organisation(site, *NORTHSIDE)
    southside = _ensure_organisation(site, *SOUTHSIDE)
    notes = _cleanup(site, northside)

    cohort_a = _ensure_cohort(site, northside, COHORT_A)
    cohort_b = _ensure_cohort(site, northside, COHORT_B)
    cohort_empty = _ensure_cohort(site, northside, COHORT_EMPTY)
    cohort_s = _ensure_cohort(site, southside, COHORT_S)

    # Cohort Empty: no members, no registrations, ever.
    CohortMembership._base_manager.filter(cohort=cohort_empty).delete()
    CohortCourseRegistration._base_manager.filter(cohort=cohort_empty).delete()

    # --- Learners -------------------------------------------------------
    a1 = _ensure_user(site, "learner.a1@qa.test", "Alice", "Aone")
    a2 = _ensure_user(site, "learner.a2@qa.test", "Andile", "Atwo")
    b1 = _ensure_user(site, "learner.b1@qa.test", "Bongi", "Bone")
    none = _ensure_user(site, "learner.none@qa.test", "Nomsa", "Nocohort")
    s1 = _ensure_user(site, "learner.s1@qa.test", "Sizwe", "Sone")
    _ensure_membership(site, cohort_a, a1)
    _ensure_membership(site, cohort_a, a2)
    _ensure_membership(site, cohort_b, b1)
    ensure_learner(none, northside)
    CohortMembership._base_manager.filter(learner__user=none).delete()
    _ensure_membership(site, cohort_s, s1)

    _ensure_cohort_registration(site, cohort_a, course)
    _ensure_cohort_registration(site, cohort_b, course)
    _ensure_user_registration(site, northside, a1, course)
    _ensure_user_registration(site, northside, b1, course)

    # --- Personas -------------------------------------------------------
    site_admin = _ensure_user(site, "site.admin@qa.test", "Sandra", "Siteadmin")
    assign_site_role(site_admin, "site_admin", site=site)
    OrganisationMember._base_manager.filter(user=site_admin).delete()

    org_admin = _ensure_user(site, "org.admin@qa.test", "Oscar", "Orgadmin")
    org_admin2 = _ensure_user(site, "org.admin2@qa.test", "Olga", "Orgadmintwo")
    lapsed = _ensure_user(site, "lapsed.admin@qa.test", "Lars", "Lapsed")
    stale = _ensure_user(site, "stale.admin@qa.test", "Stella", "Stale")
    for user in (org_admin, org_admin2, lapsed, stale):
        assign_object_role(user, northside, "organisation_admin")
    assign_object_role(stale, cohort_b, "cohort_viewer")

    cohort_admin = _ensure_user(site, "cohort.admin@qa.test", "Cora", "Cohortadmin")
    assign_object_role(cohort_admin, cohort_a, "cohort_admin")
    cohort_viewer = _ensure_user(site, "cohort.viewer@qa.test", "Vera", "Viewer")
    assign_object_role(cohort_viewer, cohort_a, "cohort_viewer")
    cohort_viewer.is_staff = True
    cohort_viewer.save(update_fields=["is_staff"])
    report_ct = ContentType.objects.get_for_model(GeneratedReport)
    cohort_viewer.user_permissions.add(
        *Permission.objects.filter(
            content_type=report_ct,
            codename__in=["view_generatedreport", "add_generatedreport"],
        )
    )

    for user in (org_admin, org_admin2, stale, cohort_admin, cohort_viewer):
        _set_member(user, northside, True)
    _set_member(lapsed, northside, False)

    report_a = _ensure_ready_report(site, cohort_a, cohort_viewer)
    report_b = _ensure_ready_report(site, cohort_b, cohort_viewer)
    gate = _clear_registration_gate(site)

    # --- Report ---------------------------------------------------------
    click.secho("--- Permissions QA data ---", fg="cyan", bold=True)
    for note in notes + ([gate] if gate else []):
        click.secho(note, fg="yellow")
    click.echo(f"Course {course.title!r} slug={course.slug} pk={course.pk}")
    for org in (northside, southside):
        click.echo(f"ORG {org.name} slug={org.slug} pk={org.pk}")
    for cohort in (cohort_a, cohort_b, cohort_empty, cohort_s):
        click.echo(
            f"COHORT {cohort.name!r} pk={cohort.pk} members="
            f"{CohortMembership._base_manager.filter(cohort=cohort).count()} regs="
            f"{CohortCourseRegistration._base_manager.filter(cohort=cohort).count()}"
        )
    for user in (a1, a2, b1, none, s1):
        learners = list(
            Learner._base_manager.filter(user=user).values_list(
                "pk", "organisation__slug"
            )
        )
        click.echo(f"LEARNER {user.email} user.pk={user.pk} learner rows={learners}")
    for report in (report_a, report_b):
        click.echo(
            f"REPORT pk={report.pk} cohort={report.cohort.name!r} status={report.status}"
        )
    click.secho("Passwords: each persona's own email address", fg="cyan")


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed.")
def command(site_name: str) -> None:
    """Seed the educator-interface permissions QA scenario."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site '{site_name}' not found.") from e
    _pin_current_site(site)
    with _site_context(site):
        _seed(site)
