"""Seed ``LearnerDeadline`` rows for the learner-deadline admin QA workflow.

``LearnerDeadline`` hangs off an individual ``LearnerCourseRegistration`` (the
``learner_course_registration`` FK), which is what makes it distinct from
``CohortDeadline`` (cohort registration) and ``LearnerCohortDeadlineOverride``
(per-user override inside a cohort). ``qa_create_deadline_overrides`` seeds the
last of those three, so before this command the ``LearnerDeadline`` changelist
was always empty and its ``list_select_related`` / ``search_fields`` /
``autocomplete_fields`` traversals were never executed.

The seeded set deliberately spans two users and three courses with a mix of
hard and soft deadlines so the "By course" and "By is hard deadline"
list filters both narrow the changelist.

Every deadline is placed in the FUTURE on purpose: an expired *hard* deadline
marks the item BLOCKED in the learner TOC and makes the player redirect away
from it, which would disturb course-player QA running against the same
learner.

Idempotent: rows are matched on the unique
(learner_course_registration, content_type, object_id) triple.
"""

from datetime import timedelta
from typing import cast

import djclick as click

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
)
from freedom_ls.learner_management.models import (
    LearnerCourseRegistration,
    LearnerDeadline,
)
from freedom_ls.organisations.utils import get_default_organisation

PRIMARY_LEARNER_EMAIL = "demodev_s1@email.com"
SECONDARY_LEARNER_EMAIL = "qa-eve.middle@example.com"

PRIMARY_COURSE_SLUG = "functionality-demo-course-parts"
SECOND_COURSE_SLUG = "functionality-demo-show-end-with-topic"
THIRD_COURSE_SLUG = "functionality-demo-show-end-with-quiz"


def _get_user(email: str) -> User:
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        raise click.ClickException(
            f"User '{email}' not found. Run the qa_ command that seeds it first."
        )
    return user


def _get_course(slug: str, site: Site) -> Course:
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        available = list(
            Course.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'. Available: {available}"
        )
    return course


def _ensure_registration(
    user: User, course: Course, site: Site
) -> LearnerCourseRegistration:
    """Return the learner's individual registration, creating it if absent.

    Never touches the ``User`` row, so passwords and sessions are left alone.
    """
    existing: LearnerCourseRegistration | None = (
        LearnerCourseRegistration.objects.filter(
            learner__user=user, course=course, site=site
        ).first()
    )
    if existing is not None:
        return existing
    registration = cast(
        LearnerCourseRegistration,
        LearnerCourseRegistrationFactory(
            learner__user=user,
            learner__organisation=get_default_organisation(site),
            course=course,
            site=site,
            is_active=True,
        ),
    )
    click.secho(
        f"  + Created LearnerCourseRegistration {user.email} -> {course.slug}",
        fg="green",
    )
    return registration


def _ensure_deadline(
    registration: LearnerCourseRegistration,
    site: Site,
    days_from_now: int,
    is_hard: bool,
    content_item: Topic | Form | None,
) -> tuple[LearnerDeadline, bool]:
    """Create the LearnerDeadline if the unique triple is not already taken."""
    content_type = (
        DjangoContentType.objects.get_for_model(content_item) if content_item else None
    )
    object_id = content_item.pk if content_item else None

    existing: LearnerDeadline | None = LearnerDeadline.objects.filter(
        learner_course_registration=registration,
        content_type=content_type,
        object_id=object_id,
        site=site,
    ).first()
    if existing is not None:
        return existing, False

    factory_kwargs: dict[str, object] = {
        "learner_course_registration": registration,
        "site": site,
        "deadline": timezone.now() + timedelta(days=days_from_now),
        "is_hard_deadline": is_hard,
    }
    if content_item is not None:
        factory_kwargs["content_item"] = content_item
    return cast(LearnerDeadline, LearnerDeadlineFactory(**factory_kwargs)), True


def _first_topic(course: Course) -> Topic | None:
    for item in course.viewable_items():
        if isinstance(item, Topic):
            return item
    return None


def _first_form(course: Course) -> Form | None:
    for item in course.viewable_items():
        if isinstance(item, Form):
            return item
    return None


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed LearnerDeadline rows for the learner-deadline admin QA workflow.

    SITE_NAME is the name of the site to seed (e.g. 'DemoDev').
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    primary = _get_user(PRIMARY_LEARNER_EMAIL)
    secondary = _get_user(SECONDARY_LEARNER_EMAIL)

    course_one = _get_course(PRIMARY_COURSE_SLUG, site)
    course_two = _get_course(SECOND_COURSE_SLUG, site)
    course_three = _get_course(THIRD_COURSE_SLUG, site)

    click.secho("Ensuring individual course registrations:", fg="cyan")
    reg_primary_one = _ensure_registration(primary, course_one, site)
    reg_primary_two = _ensure_registration(primary, course_two, site)
    reg_secondary_three = _ensure_registration(secondary, course_three, site)
    reg_secondary_one = _ensure_registration(secondary, course_one, site)

    # (registration, days, is_hard, content_item, human label)
    plan: list[tuple[LearnerCourseRegistration, int, bool, Topic | Form | None]] = [
        (reg_primary_one, 30, True, None),
        (reg_primary_one, 21, False, _first_form(course_one)),
        (reg_primary_one, 45, True, _first_topic(course_one)),
        (reg_primary_two, 25, False, None),
        (reg_secondary_three, 35, True, None),
        (reg_secondary_three, 40, False, _first_topic(course_three)),
        (reg_secondary_one, 28, False, _first_topic(course_one)),
    ]

    click.secho("\nSeeding LearnerDeadline rows:", fg="cyan")
    created = 0
    for registration, days, is_hard, content_item in plan:
        deadline, was_created = _ensure_deadline(
            registration, site, days, is_hard, content_item
        )
        created += int(was_created)
        target = str(content_item) if content_item else "Whole course"
        kind = "hard" if is_hard else "soft"
        verb = "created" if was_created else "exists"
        click.secho(
            f"  {verb:8} {registration.learner.user.email:32} "
            f"{registration.course.slug:40} {target:28} {kind:4} "
            f"{deadline.deadline:%Y-%m-%d}",
            fg="green" if was_created else "yellow",
        )

    total = LearnerDeadline.objects.filter(site=site).count()
    course_slugs = sorted(
        set(
            LearnerDeadline.objects.filter(site=site).values_list(
                "learner_course_registration__course__slug", flat=True
            )
        )
    )
    learners = sorted(
        set(
            LearnerDeadline.objects.filter(site=site).values_list(
                "learner_course_registration__learner__user__email", flat=True
            )
        )
    )

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site:              {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Rows created:      {created}", fg="cyan")
    click.secho(f"LearnerDeadlines:  {total} on this site", fg="cyan")
    click.secho(f"Learners involved: {learners}", fg="cyan")
    click.secho(f"Courses involved:  {course_slugs}", fg="cyan")
    click.secho(
        "Changelist:        /admin/freedom_ls_learner_management/learnerdeadline/",
        fg="cyan",
    )
