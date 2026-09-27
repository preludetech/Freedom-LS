"""Give educator-interface QA learners cohort-granted progress with a percentage.

Builds on ``qa_create_educator_modal_target`` (run that first). For each target
learner it ensures a cohort-granted CourseProgress record on
"Content Widgets - Demo Reference" with ``last_accessed_time`` set an hour ago
and the first topic of the course completed, so a partial percentage shows:

- qa_modal_learner@example.com via "QA Modal Cohort" (makes that cohort
  undeletable: it still has a course progress record).
- demodev_s1@email.com and demodev_s2@email.com via "Cohort 2025.03.04", which
  is registered on the course if it is not already. demodev_s1 is also made a
  member of "Cohort 2025.04.06".

Idempotent: re-running reuses existing registrations, memberships and records.
"""

from datetime import timedelta
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
)
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.signals import recalculate_progress_percentage

COURSE_TITLE = "Content Widgets - Demo Reference"
MODAL_COHORT = "QA Modal Cohort"
MAIN_COHORT = "Cohort 2025.03.04"
SECOND_COHORT = "Cohort 2025.04.06"
TARGETS: list[tuple[str, str]] = [
    ("qa_modal_learner@example.com", MODAL_COHORT),
    ("demodev_s1@email.com", MAIN_COHORT),
    ("demodev_s2@email.com", MAIN_COHORT),
]


def _cohort(site: Site, name: str) -> Cohort:
    cohort: Cohort | None = Cohort.objects.filter(site=site, name=name).first()
    if cohort is None:
        raise click.ClickException(f"Cohort '{name}' not found on {site.name}.")
    return cohort


def _learner(site: Site, email: str) -> Learner:
    learner: Learner | None = Learner.objects.filter(
        site=site, user__email=email
    ).first()
    if learner is None:
        raise click.ClickException(f"Learner '{email}' not found on {site.name}.")
    return learner


def _ensure_membership(site: Site, learner: Learner, cohort: Cohort) -> None:
    if not CohortMembership.objects.filter(learner=learner, cohort=cohort).exists():
        CohortMembershipFactory(learner=learner, cohort=cohort, site=site)
        click.secho(f"Added {learner.user.email} to '{cohort.name}'", fg="green")


def _ensure_registration(
    site: Site, cohort: Cohort, course: Course
) -> CohortCourseRegistration:
    registration = CohortCourseRegistration.objects.filter(
        cohort=cohort, course=course
    ).first()
    if registration is None:
        registration = cast(
            CohortCourseRegistration,
            CohortCourseRegistrationFactory(cohort=cohort, course=course, site=site),
        )
        click.secho(f"Registered '{cohort.name}' on '{course.title}'", fg="green")
    return registration


def _ensure_record(
    site: Site, learner: Learner, registration: CohortCourseRegistration
) -> CourseProgress:
    # The registration/membership signals normally mint this record on commit.
    record = CourseProgress.objects.filter(
        learner=learner, cohort_registration=registration
    ).first()
    if record is None:
        record = cast(
            CourseProgress,
            CourseProgressFactory(
                learner=learner,
                course=registration.course,
                cohort_registration=registration,
                learner_registration=None,
                site=site,
            ),
        )
    return record


def _complete_first_topic(site: Site, record: CourseProgress) -> None:
    for item in record.course.viewable_collection_items():
        if isinstance(item.child, Topic):
            if not TopicProgress.objects.filter(
                course_progress=record, collection_item=item
            ).exists():
                TopicProgressFactory(
                    course_progress=record,
                    topic=item.child,
                    collection_item=item,
                    complete_time=timezone.now() - timedelta(hours=1),
                    site=site,
                )
            return
    raise click.ClickException(f"'{record.course.title}' has no viewable topic.")


@click.command()
@click.argument("site_name")
def command(site_name: str) -> None:
    """Seed cohort-granted partial progress for educator-interface QA."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site '{site_name}' not found.") from e

    course = Course.objects.filter(site=site, title=COURSE_TITLE).first()
    if course is None:
        raise click.ClickException(f"Course '{COURSE_TITLE}' not found.")

    _ensure_membership(
        site, _learner(site, "demodev_s1@email.com"), _cohort(site, SECOND_COHORT)
    )

    accessed = timezone.now() - timedelta(hours=1)
    for email, cohort_name in TARGETS:
        learner = _learner(site, email)
        cohort = _cohort(site, cohort_name)
        _ensure_membership(site, learner, cohort)
        registration = _ensure_registration(site, cohort, course)
        record = _ensure_record(site, learner, registration)
        _complete_first_topic(site, record)
        recalculate_progress_percentage(record)
        record.started_at = record.started_at or accessed
        record.last_accessed_time = accessed
        record.save(update_fields=["started_at", "last_accessed_time"])
        click.secho(
            f"{email}: CourseProgress {record.pk} via '{cohort.name}' "
            f"{record.progress_percentage}% last accessed {accessed:%H:%M}",
            fg="cyan",
        )
