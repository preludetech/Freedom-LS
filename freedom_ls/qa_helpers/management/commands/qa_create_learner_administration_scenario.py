"""Seed the browser-QA data set for educator-interface learner administration.

Builds spec_dd/.../educator-interface-7-learner-administration/3. frontend_qa.md
§0.2: Course Pub / Hid / Soon / Other, organisations Northside and Southside
beside the site's default organisation, Cohorts A / B / C / Old / S, the
learners (active, nameless, pending, deactivated, cohort-less, default-org,
other-site) with their course progress records, and the educator personas.

Every persona except the pending one has its own email address as password and
a verified primary EmailAddress. Idempotent: re-running reuses existing rows.

Usage:
    uv run python manage.py qa_create_learner_administration_scenario
    uv run python manage.py qa_create_learner_administration_scenario --site-name DemoDev
"""

from __future__ import annotations

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.account_setup import match_or_create_user
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import SiteSignupPolicy, User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CourseVisibility, Topic
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.learner_actions import deactivate_learner
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_cohort_registration,
    _ensure_member,
    _ensure_organisation,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.utils import assign_object_role


def _ensure_course(site: Site, title: str, visibility: str, topics: int) -> Course:
    course: Course | None = Course._base_manager.filter(site=site, title=title).first()
    if course is None:
        course = cast(
            Course, CourseFactory(site=site, title=title, visibility=visibility)
        )
    elif course.visibility != visibility:
        course.visibility = visibility
        course.save(update_fields=["visibility"])
    for n in range(1, topics + 1):
        topic_title = f"{title} Topic {n}"
        if Topic._base_manager.filter(site=site, title=topic_title).exists():
            continue
        topic = TopicFactory(site=site, title=topic_title)
        ContentCollectionItemFactory(
            site=site, collection_object=course, child_object=topic, order=n - 1
        )
    return course


def _ensure_user(site: Site, email: str, first_name: str, last_name: str) -> User:
    """A login-ready user: password = email, verified primary EmailAddress."""
    user: User | None = User._base_manager.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site, email=email, first_name=first_name, last_name=last_name
            ),
        )
    else:
        user.is_active = True
        user.first_name = first_name
        user.last_name = last_name
        user.set_password(email)
        user.save(update_fields=["is_active", "first_name", "last_name", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_individual_registration(
    site: Site, learner: Learner, course: Course
) -> LearnerCourseRegistration:
    reg: LearnerCourseRegistration | None = (
        LearnerCourseRegistration._base_manager.filter(
            learner=learner, course=course
        ).first()
    )
    if reg is None:
        reg = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                site=site, learner=learner, course=course, is_active=True
            ),
        )
    return reg


def _ensure_progress(
    site: Site,
    learner: Learner,
    course: Course,
    cohort_registration: CohortCourseRegistration,
    percentage: int,
) -> CourseProgress:
    """The record for this learner under this cohort registration, at `percentage`.

    The membership signal normally mints the row on commit; a record without a
    membership (ben under Cohort A) is built by the factory.
    """
    progress: CourseProgress | None = CourseProgress._base_manager.filter(
        learner=learner, cohort_registration=cohort_registration
    ).first()
    if progress is None:
        progress = cast(
            CourseProgress,
            CourseProgressFactory(
                site=site,
                learner=learner,
                course=course,
                learner_registration=None,
                cohort_registration=cohort_registration,
            ),
        )
    progress.progress_percentage = percentage
    progress.last_accessed_time = None
    progress.save(update_fields=["progress_percentage", "last_accessed_time"])
    return progress


def _seed(site: Site) -> None:
    pub = _ensure_course(site, "Course Pub", CourseVisibility.PUBLISHED, topics=3)
    hid = _ensure_course(site, "Course Hid", CourseVisibility.HIDDEN, topics=1)
    soon = _ensure_course(site, "Course Soon", CourseVisibility.COMING_SOON, topics=1)
    other = _ensure_course(site, "Course Other", CourseVisibility.HIDDEN, topics=1)

    north = _ensure_organisation(site, "Northside", "northside")
    south = _ensure_organisation(site, "Southside", "southside")
    default_org = get_default_organisation(site)

    cohort_a = _ensure_cohort(site, north, "Cohort A")
    cohort_b = _ensure_cohort(site, north, "Cohort B")
    cohort_c = _ensure_cohort(site, north, "Cohort C")
    cohort_old = _ensure_cohort(site, north, "Cohort Old", is_active=False)
    cohort_s = _ensure_cohort(site, south, "Cohort S")

    a_pub = _ensure_cohort_registration(site, cohort_a, pub)
    _ensure_cohort_registration(site, cohort_a, hid)
    b_pub = _ensure_cohort_registration(site, cohort_b, pub)
    _ensure_cohort_registration(site, cohort_c, hid)
    _ensure_cohort_registration(site, cohort_old, pub)
    _ensure_cohort_registration(site, cohort_s, other)

    ada = _ensure_user(site, "ada@qa.test", "Ada", "Lovelace")
    nameless = _ensure_user(site, "nameless@qa.test", "", "")
    pending, _ = match_or_create_user(site, "pending@qa.test", "Pending", "Person")
    ben = _ensure_user(site, "ben@qa.test", "Ben", "Brown")
    pick = _ensure_user(site, "pick@qa.test", "Pat", "Pick")
    old = _ensure_user(site, "old@qa.test", "Olga", "Old")
    removed = _ensure_user(site, "removed@qa.test", "Rae", "Removed")
    solo = _ensure_user(site, "solo@qa.test", "Sol", "Solo")
    dflt = _ensure_user(site, "dflt@qa.test", "Dee", "Default")
    south_user = _ensure_user(site, "south@qa.test", "Sam", "South")
    other_site = Site.objects.exclude(pk=site.pk).order_by("name").first()
    if other_site is None:
        raise click.ClickException("No second Site exists for away@qa.test.")
    away = _ensure_user(other_site, "away@qa.test", "Avery", "Away")

    for user in (ada, nameless, pending, removed):
        _ensure_member(site, cohort_a, user)
    _ensure_member(site, cohort_b, ben)
    _ensure_member(site, cohort_b, pick)
    _ensure_member(site, cohort_old, old)
    _ensure_member(site, cohort_s, south_user)

    removed_learner = Learner._base_manager.get(user=removed, organisation=north)
    deactivate_learner(removed_learner)

    solo_learner = ensure_learner(solo, north)
    _ensure_individual_registration(site, solo_learner, pub)
    dflt_learner = ensure_learner(dflt, default_org)
    _ensure_individual_registration(site, dflt_learner, pub)

    ada_learner = Learner._base_manager.get(user=ada, organisation=north)
    ben_learner = Learner._base_manager.get(user=ben, organisation=north)
    _ensure_progress(site, ada_learner, pub, a_pub, 40)
    _ensure_progress(site, ben_learner, pub, b_pub, 10)
    _ensure_progress(site, ben_learner, pub, a_pub, 70)

    org_admin = _ensure_user(site, "org.admin@qa.test", "Orla", "Admin")
    assign_object_role(org_admin, north, "organisation_admin")
    cohort_admin = _ensure_user(site, "cohort.admin@qa.test", "Cole", "Admin")
    assign_object_role(cohort_admin, cohort_a, "cohort_admin")
    assign_object_role(cohort_admin, cohort_b, "cohort_admin")
    cohort_viewer = _ensure_user(site, "cohort.viewer@qa.test", "Vera", "Viewer")
    assign_object_role(cohort_viewer, cohort_a, "cohort_viewer")
    south_admin = _ensure_user(site, "south.admin@qa.test", "Sid", "Admin")
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

    _report(
        [pub, hid, soon, other],
        [north, south, default_org],
        [cohort_a, cohort_b, cohort_c, cohort_old, cohort_s],
        away,
    )


def _report(
    courses: list[Course],
    orgs: list[Organisation],
    cohorts: list[Cohort],
    away: User,
) -> None:
    click.secho("--- Learner administration QA data ---", fg="cyan", bold=True)
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
    for learner in (
        Learner._base_manager.filter(user__email__endswith="@qa.test")
        .select_related("user", "organisation")
        .order_by("user__email")
    ):
        click.echo(
            f"LEARNER {learner.user.email} pk={learner.pk} "
            f"org={learner.organisation.slug} active={learner.is_active}"
        )
    for p in (
        CourseProgress._base_manager.filter(learner__user__email__endswith="@qa.test")
        .select_related("learner__user", "course", "cohort_registration__cohort")
        .order_by("learner__user__email", "course__title")
    ):
        grant = (
            p.cohort_registration.cohort.name if p.cohort_registration else "individual"
        )
        click.echo(
            f"PROGRESS {p.learner.user.email} {p.course.title} via {grant} "
            f"pct={p.progress_percentage} last_accessed={p.last_accessed_time}"
        )
    click.echo(f"AWAY {away.email} site={away.site.name}")


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed (default: DemoDev).")
def command(site_name: str) -> None:
    """Seed courses, organisations, cohorts, learners and personas for learner administration QA."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site '{site_name}' not found.") from e
    _pin_current_site(site)
    with _site_context(site):
        _seed(site)
