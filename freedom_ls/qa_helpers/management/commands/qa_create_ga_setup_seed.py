"""Seed QA data for the google-analytics-setup frontend QA plan (section 0.2).

Idempotent. Assumes ``create_demo_data`` and
``content_save demo_content <SITE_NAME>`` have already been run.

Creates / resets on SITE_NAME (default DemoDev):

1. Learner A (``qa-learner-a@email.com``): registered for a short, form-free
   demo course, with its CourseProgress reset to a freshly-registered state
   (started_at / completed_time etc. null) and no TopicProgress for it.
2. Learner B (``qa-learner-b@email.com``): no CourseApplication rows.
3. An application-gated course with NO application form and one topic.
4. A coming-soon course nobody has expressed interest in.
5. A free course Learner B is NOT registered for (registration and progress
   deleted on a re-run), for the self-registration check.
6. A second free course Learner A is registered for with fresh progress, for
   the two-courses-in-one-session check.
7. Learner C (``qa-learner-c@email.com``): granted a course through a cohort
   registration only, with fresh progress.

Each course's slug and UUID is printed, because the QA plan compares the
``course_id`` event parameter against the UUID.

All learners are non-staff, have a verified primary email, and their
password equals their email.
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_interest.models import CourseInterest
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
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.organisations.utils import get_default_organisation

LEARNER_A_EMAIL = "qa-learner-a@email.com"
LEARNER_B_EMAIL = "qa-learner-b@email.com"
LEARNER_C_EMAIL = "qa-learner-c@email.com"

# Three topics, no forms: quick to "Next" through to "Finish Course".
LEARNER_A_COURSE_SLUG = "standard-markdown-demo-finance"

NO_FORM_GATED_TITLE = "QA Application-Gated Course (No Form)"
NO_FORM_GATED_SLUG = "qa-application-gated-course-no-form"

COMING_SOON_TITLE = "QA Coming Soon Course"
COMING_SOON_SLUG = "qa-coming-soon-course"

SELF_REGISTRATION_TITLE = "QA Free Course (Self-Registration)"
SELF_REGISTRATION_SLUG = "qa-free-course-self-registration"

SECOND_COURSE_TITLE = "QA Second Course"
SECOND_COURSE_SLUG = "qa-second-course"

COHORT_COURSE_TITLE = "QA Cohort Course"
COHORT_COURSE_SLUG = "qa-cohort-course"
COHORT_NAME = "QA GA Cohort"

FREE = {"access_type": "free"}


def _get_or_create_learner(site: Site, email: str, last_name: str) -> User:
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name="QA",
                last_name=last_name,
                password=email,
                site=site,
            ),
        )
    else:
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(email)
        user.save(update_fields=["is_active", "is_staff", "is_superuser", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


def _get_course(site: Site, slug: str) -> Course:
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        raise click.ClickException(
            f"Course '{slug}' not found on '{site.name}'. Run content_save first."
        )
    return course


def _get_or_create_qa_course(
    site: Site,
    *,
    title: str,
    slug: str,
    access_config: dict[str, str],
    visibility: CourseVisibility = CourseVisibility.PUBLISHED,
) -> Course:
    """A one-topic course, brought back to the given config on a re-run."""
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        course = cast(
            Course,
            CourseFactory(
                title=title,
                slug=slug,
                access_config=access_config,
                visibility=visibility,
                site=site,
            ),
        )
    else:
        course.access_config = access_config
        course.visibility = visibility
        course.save(update_fields=["access_config", "visibility"])
    if not course.viewable_items():
        topic = TopicFactory(
            title=f"{title} - Intro",
            content=f"# Welcome\n\nQA topic for {title}.",
            site=site,
        )
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, site=site
        )
    return course


def _reset_progress(record: CourseProgress) -> None:
    """Back to a freshly-registered state: never started, nothing read."""
    TopicProgress.objects.filter(course_progress=record).delete()
    record.started_at = None
    record.completed_time = None
    record.last_accessed_item = None
    record.last_accessed_time = None
    record.progress_percentage = 0
    record.save(
        update_fields=[
            "started_at",
            "completed_time",
            "last_accessed_item",
            "last_accessed_time",
            "progress_percentage",
        ]
    )


def _register_with_fresh_progress(site: Site, user: User, course: Course) -> None:
    if not LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course, site=site, is_active=True
    ).exists():
        LearnerCourseRegistrationFactory(
            learner__user=user,
            learner__organisation=get_default_organisation(site),
            course=course,
            site=site,
        )
    record = course_progress_for(user, course)
    if record is None:
        raise click.ClickException(
            f"{user.email} has no CourseProgress record for '{course.slug}'."
        )
    _reset_progress(record)


def _unregister(user: User, course: Course) -> None:
    """Progress goes first: CourseProgress PROTECTs the registration it hangs off."""
    records = CourseProgress.objects.filter(learner__user=user, course=course)
    TopicProgress.objects.filter(course_progress__in=records).delete()
    records.delete()
    LearnerCourseRegistration.objects.filter(learner__user=user, course=course).delete()


def _register_through_cohort(site: Site, user: User, course: Course) -> None:
    organisation = get_default_organisation(site)
    learner = ensure_learner(user, organisation)
    cohort: Cohort | None = Cohort.objects.filter(name=COHORT_NAME, site=site).first()
    if cohort is None:
        cohort = cast(
            Cohort,
            CohortFactory(name=COHORT_NAME, organisation=organisation, site=site),
        )
    if not CohortMembership.objects.filter(learner=learner, cohort=cohort).exists():
        CohortMembershipFactory(learner=learner, cohort=cohort, site=site)
    if not CohortCourseRegistration.objects.filter(
        cohort=cohort, course=course
    ).exists():
        CohortCourseRegistrationFactory(cohort=cohort, course=course, site=site)
    # No record yet is fine: the player mints one on the learner's first visit.
    record = course_progress_for(user, course)
    if record is not None:
        _reset_progress(record)


def _describe(course: Course) -> str:
    return f"'{course.title}' slug={course.slug} id={course.id}"


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create the GA-setup QA seed on SITE_NAME (default: DemoDev)."""
    site = Site.objects.filter(name=site_name).first()
    if site is None:
        raise click.ClickException(f"Site '{site_name}' not found.")

    learner_a = _get_or_create_learner(site, LEARNER_A_EMAIL, "Learner A")
    course_a = _get_course(site, LEARNER_A_COURSE_SLUG)
    _register_with_fresh_progress(site, learner_a, course_a)
    second_course = _get_or_create_qa_course(
        site, title=SECOND_COURSE_TITLE, slug=SECOND_COURSE_SLUG, access_config=FREE
    )
    _register_with_fresh_progress(site, learner_a, second_course)

    learner_b = _get_or_create_learner(site, LEARNER_B_EMAIL, "Learner B")
    CourseApplication.objects.filter(user=learner_b).delete()
    gated_no_form = _get_or_create_qa_course(
        site,
        title=NO_FORM_GATED_TITLE,
        slug=NO_FORM_GATED_SLUG,
        access_config={"access_type": "application_gated"},
    )
    coming_soon = _get_or_create_qa_course(
        site,
        title=COMING_SOON_TITLE,
        slug=COMING_SOON_SLUG,
        access_config=FREE,
        visibility=CourseVisibility.COMING_SOON,
    )
    # Everyone's, not one learner's: two QA learners express interest in a run.
    CourseInterest.objects.filter(course=coming_soon).delete()
    self_registration = _get_or_create_qa_course(
        site,
        title=SELF_REGISTRATION_TITLE,
        slug=SELF_REGISTRATION_SLUG,
        access_config=FREE,
    )
    _unregister(learner_b, self_registration)

    learner_c = _get_or_create_learner(site, LEARNER_C_EMAIL, "Learner C")
    cohort_course = _get_or_create_qa_course(
        site, title=COHORT_COURSE_TITLE, slug=COHORT_COURSE_SLUG, access_config=FREE
    )
    _register_through_cohort(site, learner_c, cohort_course)

    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(
        f"Learner A pk={learner_a.pk} {learner_a.email}: fresh progress on "
        f"{_describe(course_a)} items={len(course_a.viewable_items())} "
        f"and on {_describe(second_course)}",
        fg="green",
    )
    click.secho(
        f"Learner B pk={learner_b.pk} {learner_b.email}: no applications, "
        f"not registered for {_describe(self_registration)}",
        fg="green",
    )
    click.secho(
        f"Learner C pk={learner_c.pk} {learner_c.email}: cohort '{COHORT_NAME}' "
        f"grants {_describe(cohort_course)}",
        fg="green",
    )
    click.secho(f"No-form gated course: {_describe(gated_no_form)}", fg="green")
    click.secho(
        f"Coming-soon course, no interest: {_describe(coming_soon)}", fg="green"
    )
