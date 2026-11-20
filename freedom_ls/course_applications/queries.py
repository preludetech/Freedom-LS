"""Query helpers for course_applications.

These helpers are consumed by the ApplicationCourseAccessBackend and this app's own
views. learner_interface must NOT import from here — it reaches the applications
panel only through backend.get_dashboard_contributions().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Case, IntegerField, Value, When

from freedom_ls.organisations.utils import get_default_organisation

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_applications.models import CourseApplication
    from freedom_ls.organisations.models import Organisation

    type RequestUser = User | AnonymousUser


def organisation_for_new_application(course: Course) -> Organisation:
    """The organisation that reviews an application to `course`.

    The course's owner when it has exactly one; otherwise the site default.
    Not `Course.single_organisation()`, which returns None for the default
    organisation.
    """
    owners = list(course.organisations.all()[:2])
    if len(owners) == 1:
        return owners[0]
    return get_default_organisation(course.site)


def get_application_for_course(
    *, user: RequestUser, course: Course
) -> CourseApplication | None:
    """Return this user's application to the given course, or None.

    Returns None immediately for anonymous users — no DB query is issued.
    Site isolation is automatic via SiteAwareManager. An account holds at most
    one active application per course, whether it applied signed in or claimed
    one, beside any number of closed ones. The active application wins; with
    only closed ones, the newest is returned.
    """
    if not user.is_authenticated:
        return None
    from freedom_ls.course_applications.models import (
        ACTIVE_STATES,
        CourseApplication,
    )

    is_closed = Case(
        When(state__in=ACTIVE_STATES, then=Value(0)),
        default=Value(1),
        output_field=IntegerField(),
    )
    return (
        CourseApplication.objects.filter(user=user, course=course)
        .select_related("form_progress")
        .order_by(is_closed, "-created_at", "pk")
        .first()
    )


def panel_rows(
    applications: QuerySet[CourseApplication],
) -> QuerySet[CourseApplication]:
    """Order ``applications`` newest first and load what each panel row reads.

    The primary key breaks ties, so applications created in the same instant
    keep one stable order from page to page.
    """
    return (
        applications.select_related("course", "form_progress")
        .prefetch_related("course__organisations")
        .order_by("-created_at", "pk")
    )


def get_active_applications(user: RequestUser) -> QuerySet[CourseApplication]:
    """Return all applications for this user on the current site, newest first.

    Returns an empty queryset immediately for anonymous users — no DB query is issued.
    Site isolation is automatic via SiteAwareManager. With no terminal states
    yet, this returns all of the user's applications; it narrows to active states
    once withdraw/approve/reject exist.
    """
    from freedom_ls.course_applications.models import CourseApplication

    if not user.is_authenticated:
        return CourseApplication.objects.none()
    return panel_rows(CourseApplication.objects.filter(user=user))
