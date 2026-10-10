"""Seed the browser-QA data set for educator-interface cohort administration.

Builds four courses (Course Pub / Hid / Soon / Other, one topic each), two
organisations (Northside, Southside), seven cohorts covering the empty,
removed-member, stale-registration and inactive-cohort edge cases, and the
educator personas (organisation_admin, cohort_admin, cohort_viewer, a lapsed
cohort_viewer whose OrganisationMember is inactive).

Every persona's password is its own email address, with a verified primary
EmailAddress. Idempotent: re-running reuses existing rows.

Usage:
    uv run python manage.py qa_create_cohort_administration_scenario
    uv run python manage.py qa_create_cohort_administration_scenario --site-name DemoDev
"""

from __future__ import annotations

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import SiteSignupPolicy, User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CourseVisibility, Topic
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
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.utils import assign_object_role


def _ensure_course(site: Site, title: str, visibility: str) -> Course:
    course: Course | None = Course._base_manager.filter(site=site, title=title).first()
    if course is None:
        course = cast(
            Course, CourseFactory(site=site, title=title, visibility=visibility)
        )
    elif course.visibility != visibility:
        course.visibility = visibility
        course.save(update_fields=["visibility"])
    topic_title = f"{title} Topic 1"
    topic: Topic | None = Topic._base_manager.filter(
        site=site, title=topic_title
    ).first()
    if topic is None:
        topic = cast(Topic, TopicFactory(site=site, title=topic_title))
        ContentCollectionItemFactory(
            site=site, collection_object=course, child_object=topic, order=0
        )
    return course


def _ensure_organisation(site: Site, name: str, slug: str) -> Organisation:
    org: Organisation | None = Organisation._base_manager.filter(
        site=site, slug=slug
    ).first()
    if org is None:
        org = cast(Organisation, OrganisationFactory(site=site, name=name, slug=slug))
    return org


def _ensure_cohort(
    site: Site, org: Organisation, name: str, is_active: bool = True
) -> Cohort:
    cohort: Cohort | None = Cohort._base_manager.filter(
        site=site, organisation=org, name=name
    ).first()
    if cohort is None:
        cohort = cast(
            Cohort,
            CohortFactory(site=site, organisation=org, name=name, is_active=is_active),
        )
    elif cohort.is_active != is_active:
        cohort.is_active = is_active
        cohort.save(update_fields=["is_active"])
    return cohort


def _ensure_user(site: Site, email: str) -> User:
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(User, UserFactory(site=site, email=email))
    else:
        user.is_active = True
        user.set_password(email)
        user.save(update_fields=["is_active", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_member(site: Site, cohort: Cohort, user: User) -> CohortMembership:
    existing: CohortMembership | None = CohortMembership._base_manager.filter(
        cohort=cohort, learner__user=user
    ).first()
    if existing is not None:
        return existing
    return cast(
        CohortMembership,
        CohortMembershipFactory(site=site, cohort=cohort, learner__user=user),
    )


def _ensure_cohort_registration(
    site: Site, cohort: Cohort, course: Course, is_active: bool = True
) -> CohortCourseRegistration:
    reg: CohortCourseRegistration | None = (
        CohortCourseRegistration._base_manager.filter(
            cohort=cohort, course=course
        ).first()
    )
    if reg is None:
        reg = cast(
            CohortCourseRegistration,
            CohortCourseRegistrationFactory(
                site=site, cohort=cohort, course=course, is_active=is_active
            ),
        )
    elif reg.is_active != is_active:
        reg.is_active = is_active
        reg.save(update_fields=["is_active"])
    return reg


def _seed(site: Site) -> None:
    pub = _ensure_course(site, "Course Pub", CourseVisibility.PUBLISHED)
    hid = _ensure_course(site, "Course Hid", CourseVisibility.HIDDEN)
    soon = _ensure_course(site, "Course Soon", CourseVisibility.COMING_SOON)
    other = _ensure_course(site, "Course Other", CourseVisibility.HIDDEN)

    north = _ensure_organisation(site, "Northside", "northside")
    south = _ensure_organisation(site, "Southside", "southside")

    cohort_a = _ensure_cohort(site, north, "Cohort A")
    cohort_b = _ensure_cohort(site, north, "Cohort B")
    cohort_empty = _ensure_cohort(site, north, "Cohort Empty")
    cohort_removed = _ensure_cohort(site, north, "Cohort Removed")
    cohort_stale = _ensure_cohort(site, north, "Cohort Stale")
    cohort_old = _ensure_cohort(site, north, "Cohort Old", is_active=False)
    cohort_s = _ensure_cohort(site, south, "Cohort S")

    a1 = _ensure_user(site, "a1@qa.test")
    a2 = _ensure_user(site, "a2@qa.test")
    a3 = _ensure_user(site, "a3@qa.test")
    old = _ensure_user(site, "old@qa.test")
    removed = _ensure_user(site, "removed@qa.test")
    s1 = _ensure_user(site, "s1@qa.test")

    for u in (a1, a2, a3):
        _ensure_member(site, cohort_a, u)
    _ensure_member(site, cohort_b, a1)
    _ensure_member(site, cohort_old, old)
    _ensure_member(site, cohort_s, s1)
    # The removed learner: membership first (while active), then deactivate.
    _ensure_member(site, cohort_removed, removed)
    Learner._base_manager.filter(user=removed, organisation=north).update(
        is_active=False
    )

    a_pub = _ensure_cohort_registration(site, cohort_a, pub)
    _ensure_cohort_registration(site, cohort_a, hid)
    _ensure_cohort_registration(site, cohort_b, hid)
    _ensure_cohort_registration(site, cohort_stale, pub, is_active=False)
    _ensure_cohort_registration(site, cohort_old, pub)
    s_other = _ensure_cohort_registration(site, cohort_s, other)

    a3_learner = ensure_learner(a3, north)
    if not LearnerCourseRegistration._base_manager.filter(
        learner=a3_learner, course=hid
    ).exists():
        LearnerCourseRegistrationFactory(
            site=site, learner=a3_learner, course=hid, is_active=True
        )

    # Progress: rows are minted on_commit by the registration/membership
    # signals (autocommit here, so they already exist).
    a1_progress = CourseProgress._base_manager.get(
        learner__user=a1, learner__organisation=north, cohort_registration=a_pub
    )
    if a1_progress.completed_time is None:
        now = timezone.now()
        a1_progress.started_at = a1_progress.started_at or now
        a1_progress.completed_time = now
        a1_progress.progress_percentage = 100
        a1_progress.save(
            update_fields=["started_at", "completed_time", "progress_percentage"]
        )
    a2_progress = CourseProgress._base_manager.get(
        learner__user=a2, learner__organisation=north, cohort_registration=a_pub
    )

    # Personas.
    org_admin = _ensure_user(site, "org.admin@qa.test")
    assign_object_role(org_admin, north, "organisation_admin")
    cohort_admin = _ensure_user(site, "cohort.admin@qa.test")
    assign_object_role(cohort_admin, cohort_a, "cohort_admin")
    cohort_viewer = _ensure_user(site, "cohort.viewer@qa.test")
    assign_object_role(cohort_viewer, cohort_a, "cohort_viewer")
    lapsed = _ensure_user(site, "lapsed.viewer@qa.test")
    assign_object_role(lapsed, cohort_a, "cohort_viewer")
    OrganisationMember._base_manager.filter(user=lapsed, organisation=north).update(
        is_active=False
    )
    south_admin = _ensure_user(site, "south.admin@qa.test")
    assign_object_role(south_admin, south, "organisation_admin")

    policy: SiteSignupPolicy | None = SiteSignupPolicy.objects.filter(site=site).first()
    if policy is not None and policy.additional_registration_forms:
        click.secho(
            f"Cleared SiteSignupPolicy.additional_registration_forms "
            f"{policy.additional_registration_forms}",
            fg="yellow",
        )
        policy.additional_registration_forms = []
        policy.save(update_fields=["additional_registration_forms"])

    click.secho("--- Cohort administration QA data ---", fg="cyan", bold=True)
    for c in (pub, hid, soon, other):
        click.echo(
            f"COURSE {c.title!r} pk={c.pk} slug={c.slug} visibility={c.visibility}"
        )
    for o in (north, south):
        click.echo(f"ORG {o.name!r} pk={o.pk} slug={o.slug}")
    for cohort in (
        cohort_a,
        cohort_b,
        cohort_empty,
        cohort_removed,
        cohort_stale,
        cohort_old,
        cohort_s,
    ):
        cohort.refresh_from_db()
        click.echo(
            f"COHORT {cohort.name!r} pk={cohort.pk} active={cohort.is_active} "
            f"members={CohortMembership._base_manager.filter(cohort=cohort).count()} "
            f"regs={list(CohortCourseRegistration._base_manager.filter(cohort=cohort).values_list('course__title', 'is_active'))}"
        )
    click.echo(f"Cohort S CohortCourseRegistration pk={s_other.pk}")
    a1_progress.refresh_from_db()
    click.echo(
        f"a1 Pub progress pk={a1_progress.pk} completed={a1_progress.completed_time} "
        f"pct={a1_progress.progress_percentage}; a2 Pub progress pk={a2_progress.pk} "
        f"completed={a2_progress.completed_time}"
    )
    click.echo(
        "OrganisationMember: "
        + str(
            list(
                OrganisationMember._base_manager.filter(
                    user__email__endswith="@qa.test"
                )
                .order_by("user__email")
                .values_list("user__email", "organisation__slug", "is_active")
            )
        )
    )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed (default: DemoDev).")
def command(site_name: str) -> None:
    """Seed courses, organisations, cohorts and personas for cohort administration QA."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site '{site_name}' not found.") from e
    _pin_current_site(site)
    with _site_context(site):
        _seed(site)
