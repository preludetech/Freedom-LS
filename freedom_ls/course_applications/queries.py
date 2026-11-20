"""Query helpers for course_applications.

These helpers are consumed by the ApplicationCourseAccessBackend and this app's own
views. learner_interface must NOT import from here — it reaches the applications
panel only through backend.get_dashboard_contributions().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When

from freedom_ls.organisations.utils import get_default_organisation

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_applications.models import CourseApplication
    from freedom_ls.organisations.models import Organisation

    type RequestUser = User | AnonymousUser


def _first(states: frozenset[str]) -> Case:
    """Sorts rows in `states` ahead of every other row."""
    return Case(
        When(state__in=states, then=Value(0)),
        default=Value(1),
        output_field=IntegerField(),
    )


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

    return (
        CourseApplication.objects.filter(user=user, course=course)
        .select_related("form_progress")
        .order_by(_first(ACTIVE_STATES), "-created_at", "pk")
        .first()
    )


def panel_rows(
    applications: QuerySet[CourseApplication],
) -> QuerySet[CourseApplication]:
    """Order ``applications`` open ones first, newest first, and load what each panel row reads.

    The primary key breaks ties, so applications created in the same instant
    keep one stable order from page to page.
    """
    from freedom_ls.course_applications.models import OPEN_STATES

    return (
        applications.select_related("course", "form_progress")
        .prefetch_related("course__organisations")
        .order_by(_first(OPEN_STATES), "-created_at", "pk")
    )


def get_dashboard_applications(user: RequestUser) -> QuerySet[CourseApplication]:
    """Return the applications the user's dashboard panel lists.

    Active applications, plus each rejected one that no newer application for
    the same course has replaced; a newer application in any state, withdrawn
    included, hides the rejection. Open applications come first, then approved
    and rejected ones, newest first within each group.

    Returns an empty queryset immediately for anonymous users — no DB query is issued.
    Site isolation is automatic via SiteAwareManager.
    """
    from freedom_ls.course_applications.models import (
        ACTIVE_STATES,
        CourseApplication,
    )

    if not user.is_authenticated:
        return CourseApplication.objects.none()
    superseded = CourseApplication.objects.filter(
        user=OuterRef("user"),
        course=OuterRef("course"),
        created_at__gt=OuterRef("created_at"),
    )
    return panel_rows(
        CourseApplication.objects.filter(user=user).filter(
            Q(state__in=ACTIVE_STATES)
            | (Q(state=CourseApplication.State.REJECTED) & ~Exists(superseded))
        )
    )
