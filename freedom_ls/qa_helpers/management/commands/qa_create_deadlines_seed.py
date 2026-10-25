"""Seed (or re-seed) the deadlines frontend QA run: §0.3 of the deadlines-1 QA plan.

Builds, on the named site:

* the superuser ``demodev@email.com`` (password = email);
* one ``SiteTimeZoneConfig``: ``Africa/Johannesburg``, zone label hidden;
* ``QA Deadlines Org`` > ``QA Deadlines Cohort`` with an active
  ``CohortCourseRegistration`` for the parts course and no cohort deadline overrides;
* four verified learners (password = email):

  - ``qa_deadline_cohort@email.com``: cohort member, parts-course record created
    2026-03-01 10:00 UTC;
  - ``qa_deadline_solo@email.com``: individual registration for the parts course, its
    record created 100 days before now; plus an individual registration for the plain course;
  - ``qa_deadline_fresh@email.com``: an individual parts-course registration made now (its
    registration and record are deleted and rebuilt on every run);
  - ``qa_deadline_none@email.com``: no registrations or memberships at all.

Every run also strips the four learners' learner deadline overrides, topic progress,
course form attempts and form sittings, and zeroes their records' percentage, start,
completion and resume pointer, so nothing is completed.

The demo content must already be loaded (``content_save demo_content <SITE>``); the
command checks the parts course's defaults and refuses to seed if they differ.

Re-running is idempotent and destructive for the four ``qa_deadline_*`` accounts only.

Usage:
    uv run python manage.py qa_create_deadlines_seed [--site-name DemoDev]
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.db.models import QuerySet
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.deadlines.models import CohortDeadlineOverride, LearnerDeadlineOverride
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.site_aware_models.models import SiteTimeZoneConfig

SUPERUSER_EMAIL = "demodev@email.com"
PARTS_SLUG = "functionality-demo-course-parts"
PLAIN_SLUG = "functionality-demo-show-end-with-topic"
TIME_ZONE = "Africa/Johannesburg"
ORG_NAME = "QA Deadlines Org"
COHORT_NAME = "QA Deadlines Cohort"
COHORT_EMAIL = "qa_deadline_cohort@email.com"
SOLO_EMAIL = "qa_deadline_solo@email.com"
FRESH_EMAIL = "qa_deadline_fresh@email.com"
NONE_EMAIL = "qa_deadline_none@email.com"
COHORT_REG_DATE = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
SOLO_DAYS_AGO = 100

#: (child title, due_date, due_time, due_days_after_registration) the content must carry.
EXPECTED_DUE_DEFAULTS: list[tuple[str, date | None, time | None, int | None]] = [
    ("Welcome", date(2024, 1, 31), None, None),
    ("What to Expect", None, None, 7),
    ("Key Ideas", None, time(17, 0), 14),
    ("Knowledge Check", None, None, 21),
    ("Course Feedback", None, None, 30),
]


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_course(site: Site, slug: str, site_name: str) -> Course:
    try:
        return Course._base_manager.get(site=site, slug=slug)
    except Course.DoesNotExist as e:
        raise click.ClickException(
            f"Course '{slug}' not on site '{site_name}'. Run: "
            f"uv run python manage.py content_save demo_content {site_name}"
        ) from e


def _check_content_defaults(course: Course) -> None:
    """Refuse to seed against content whose deadline defaults differ from the plan."""
    if course.time_limit_days != 90:
        raise click.ClickException(
            f"{course.slug} time_limit_days is {course.time_limit_days}, expected 90."
        )
    by_title = {
        str(getattr(item.child, "title", "")): item
        for item in course.viewable_collection_items()
    }
    for title, due_date, due_time, days in EXPECTED_DUE_DEFAULTS:
        item = by_title.get(title)
        actual = (
            (item.due_date, item.due_time, item.due_days_after_registration)
            if item
            else None
        )
        if actual != (due_date, due_time, days):
            raise click.ClickException(
                f"{course.slug} item '{title}' due settings {actual}, "
                f"expected {(due_date, due_time, days)}."
            )
    click.echo(f"Content defaults OK on {course.slug} (time limit 90 days).")


def _ensure_user(email: str, site: Site, superuser: bool = False) -> User:
    """A login-ready user: password = email, verified primary address, on `site`."""
    user = User._base_manager.filter(email=email).first()
    if user is None:
        user = cast(User, UserFactory(email=email, site=site, superuser=superuser))
        click.echo(f"Created user {email} (pk {user.pk}).")
    user.site = site
    user.is_active = True
    user.is_staff = superuser
    user.is_superuser = superuser
    user.set_password(email)
    user.save()
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_time_zone(site: Site) -> SiteTimeZoneConfig:
    config = SiteTimeZoneConfig._base_manager.filter(site=site).first()
    if config is None:
        return cast(
            SiteTimeZoneConfig,
            SiteTimeZoneConfigFactory(
                site=site, time_zone=TIME_ZONE, show_time_zone_to_learners=False
            ),
        )
    config.time_zone = TIME_ZONE
    config.show_time_zone_to_learners = False
    config.save()
    return config


def _ensure_cohort_registration(site: Site, course: Course) -> CohortCourseRegistration:
    organisation = Organisation._base_manager.filter(site=site, name=ORG_NAME).first()
    if organisation is None:
        organisation = cast(Organisation, OrganisationFactory(site=site, name=ORG_NAME))
    cohort = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=COHORT_NAME
    ).first()
    if cohort is None:
        cohort = cast(
            Cohort,
            CohortFactory(site=site, organisation=organisation, name=COHORT_NAME),
        )
    registration = CohortCourseRegistration._base_manager.filter(
        cohort=cohort, course=course
    ).first()
    if registration is None:
        registration = cast(
            CohortCourseRegistration,
            CohortCourseRegistrationFactory(
                site=site, cohort=cohort, course=course, is_active=True
            ),
        )
    elif not registration.is_active:
        registration.is_active = True
        registration.save()
    deleted = CohortDeadlineOverride._base_manager.filter(
        cohort_registration=registration
    ).delete()
    click.echo(f"Cohort deadline overrides removed: {deleted}")
    return registration


def _learner(user: User, organisation: Organisation, site: Site) -> Learner:
    return cast(
        Learner, LearnerFactory(user=user, organisation=organisation, site=site)
    )


def _record_for(
    learner: Learner,
    course: Course,
    site: Site,
    learner_registration: LearnerCourseRegistration | None = None,
    cohort_registration: CohortCourseRegistration | None = None,
) -> CourseProgress:
    """The record the registration's signal minted, or a factory-built one if it is missing."""
    record = CourseProgress._base_manager.filter(
        learner=learner,
        course=course,
        learner_registration=learner_registration,
        cohort_registration=cohort_registration,
    ).first()
    if record is None:
        record = cast(
            CourseProgress,
            CourseProgressFactory(
                site=site,
                learner=learner,
                course=course,
                learner_registration=learner_registration,
                cohort_registration=cohort_registration,
            ),
        )
    return record


def _individual_registration(
    learner: Learner, course: Course, site: Site
) -> LearnerCourseRegistration:
    registration = LearnerCourseRegistration._base_manager.filter(
        learner=learner, course=course
    ).first()
    if registration is None:
        return cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                site=site, learner=learner, course=course, is_active=True
            ),
        )
    if not registration.is_active:
        registration.is_active = True
        registration.save()
    return registration


def _set_created_at(record: CourseProgress, when: datetime) -> None:
    # auto_now_add overwrites created_at on insert, so write the column directly.
    CourseProgress._base_manager.filter(pk=record.pk).update(created_at=when)
    record.refresh_from_db()


def _strip_progress(users: list[User]) -> None:
    """Remove every completion, sitting and learner override the users hold."""
    records = CourseProgress._base_manager.filter(learner__user__in=users)
    for label, queryset in (
        (
            "Learner deadline overrides",
            LearnerDeadlineOverride._base_manager.filter(course_progress__in=records),
        ),
        (
            "Topic progress",
            TopicProgress._base_manager.filter(course_progress__in=records),
        ),
        (
            "Course form attempts",
            CourseFormAttempt._base_manager.filter(course_progress__in=records),
        ),
        ("Form sittings", FormProgress._base_manager.filter(user__in=users)),
    ):
        click.echo(f"{label} removed: {_delete(queryset)}")
    records.update(
        progress_percentage=0,
        started_at=None,
        completed_time=None,
        last_accessed_time=None,
        last_accessed_item=None,
    )


def _delete(queryset: QuerySet) -> tuple[int, dict[str, int]]:
    return queryset.delete()


def _wipe_enrolment(user: User) -> None:
    """Delete the user's records, then registrations and memberships (PROTECT order)."""
    click.echo(
        f"{user.email} records removed: "
        f"{_delete(CourseProgress._base_manager.filter(learner__user=user))}"
    )
    click.echo(
        f"{user.email} registrations removed: "
        f"{_delete(LearnerCourseRegistration._base_manager.filter(learner__user=user))}"
    )
    click.echo(
        f"{user.email} memberships removed: "
        f"{_delete(CohortMembership._base_manager.filter(learner__user=user))}"
    )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site the data belongs to.")
def command(site_name: str) -> None:
    """Seed the deadlines QA run on SITE_NAME."""
    site = _get_site(site_name)
    parts = _get_course(site, PARTS_SLUG, site_name)
    plain = _get_course(site, PLAIN_SLUG, site_name)
    _check_content_defaults(parts)

    _ensure_user(SUPERUSER_EMAIL, site, superuser=True)
    tz_config = _ensure_time_zone(site)
    cohort_registration = _ensure_cohort_registration(site, parts)
    organisation = cohort_registration.cohort.organisation

    cohort_user = _ensure_user(COHORT_EMAIL, site)
    solo_user = _ensure_user(SOLO_EMAIL, site)
    fresh_user = _ensure_user(FRESH_EMAIL, site)
    none_user = _ensure_user(NONE_EMAIL, site)

    _strip_progress([cohort_user, solo_user, fresh_user, none_user])
    _wipe_enrolment(fresh_user)
    _wipe_enrolment(none_user)

    cohort_learner = _learner(cohort_user, organisation, site)
    if not CohortMembership._base_manager.filter(
        learner=cohort_learner, cohort=cohort_registration.cohort
    ).exists():
        CohortMembershipFactory(
            site=site, learner=cohort_learner, cohort=cohort_registration.cohort
        )
    cohort_record = _record_for(
        cohort_learner, parts, site, cohort_registration=cohort_registration
    )
    _set_created_at(cohort_record, COHORT_REG_DATE)

    solo_learner = _learner(solo_user, organisation, site)
    solo_parts = _individual_registration(solo_learner, parts, site)
    solo_record = _record_for(
        solo_learner, parts, site, learner_registration=solo_parts
    )
    _set_created_at(solo_record, timezone.now() - timedelta(days=SOLO_DAYS_AGO))
    solo_plain = _individual_registration(solo_learner, plain, site)
    solo_plain_record = _record_for(
        solo_learner, plain, site, learner_registration=solo_plain
    )

    fresh_learner = _learner(fresh_user, organisation, site)
    fresh_registration = _individual_registration(fresh_learner, parts, site)
    fresh_record = _record_for(
        fresh_learner, parts, site, learner_registration=fresh_registration
    )

    click.echo(f"\nSite time zone: {tz_config.pk} {tz_config}")
    click.echo(
        f"Cohort {cohort_registration.cohort.pk}; "
        f"cohort registration {cohort_registration.pk}"
    )
    for label, record in (
        ("cohort / parts", cohort_record),
        ("solo / parts", solo_record),
        ("solo / plain", solo_plain_record),
        ("fresh / parts", fresh_record),
    ):
        click.echo(
            f"{label}: CourseProgress {record.pk} created_at {record.created_at}"
        )
    click.echo("All passwords equal the email address.")
