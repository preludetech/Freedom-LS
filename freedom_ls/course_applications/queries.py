"""Query helpers for course_applications.

These helpers are consumed by the ApplicationCourseAccessBackend and this app's own
views. learner_interface must NOT import from here — it reaches the applications
panel only through backend.get_dashboard_contributions().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.db.models import Case, QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_applications.models import CourseApplication

    type RequestUser = User | AnonymousUser


def _submitted_first() -> Case:
    """An ordering term that ranks a submitted application ahead of a draft.

    The same rule as CourseApplication.is_submitted: no sitting, or a
    completed one. A no-sitting application has a NULL completed_time through
    the join too, so a plain nulls-last ordering cannot express it.
    """
    from django.db.models import Case, IntegerField, Q, Value, When

    return Case(
        When(
            Q(form_progress__isnull=True)
            | Q(form_progress__completed_time__isnull=False),
            then=Value(0),
        ),
        default=Value(1),
        output_field=IntegerField(),
    )


def get_application_for_course(
    *, user: RequestUser, course: Course
) -> CourseApplication | None:
    """Return this user's application to the given course, or None.

    Returns None immediately for anonymous users — no DB query is issued.
    Site isolation is automatic via SiteAwareManager. An account may hold two
    applications for one course once a claim attaches a second. A submitted
    one is the live one ahead of any draft, because the draft can only be a
    duplicate of a request already made; among equals the newer wins.
    """
    if not user.is_authenticated:
        return None
    from freedom_ls.course_applications.models import CourseApplication

    return (
        CourseApplication.objects.filter(user=user, course=course)
        .order_by(_submitted_first(), "-created_at")
        .first()
    )


def get_active_applications(user: RequestUser) -> QuerySet[CourseApplication]:
    """Return this user's applications on the current site, one per course.

    Returns an empty queryset immediately for anonymous users — no DB query is issued.
    Site isolation is automatic via SiteAwareManager. Where an account holds
    two applications for one course, the one `get_application_for_course`
    would pick is listed and the other is not: a dashboard that showed both
    would call one course pending and incomplete at once. With no terminal
    states yet, this returns all of the user's courses; it narrows to active
    states once withdraw/approve/reject exist.

    DISTINCT ON leaves the rows in course-id order; a caller that wants
    another order has to wrap the result in `filter(pk__in=...)`.
    """
    from freedom_ls.course_applications.models import CourseApplication

    if not user.is_authenticated:
        return CourseApplication.objects.none()
    return (
        CourseApplication.objects.filter(user=user)
        .select_related("course", "form_progress")
        .order_by("course_id", _submitted_first(), "-created_at")
        .distinct("course_id")
    )
