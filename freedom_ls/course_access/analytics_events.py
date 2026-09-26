"""The analytics events recorded along the course funnel.

Views call the `record_*` functions here and never build an analytics event
themselves, so event names and parameters are decided in one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from freedom_ls.base.analytics_events import AnalyticsEvent, record_analytics_event
from freedom_ls.course_access import get_course_access_backend

if TYPE_CHECKING:
    from django.http import HttpRequest

    from freedom_ls.content_engine.models import Course


def course_event_params(course: Course) -> dict[str, str]:
    """Which course an analytics event was about, and how that course is entered.

    `course_id` is the UUID the course webhooks carry, so GA4 data joins to
    webhook data and survives a slug rename. `course_slug` is the readable one
    and matches the page URLs GA4 already records.
    """
    return {
        "course_slug": course.slug,
        "course_id": str(course.id),
        "access_type": get_course_access_backend().get_access_type(course=course),
    }


def _record_course_access_requested(
    request: HttpRequest, course: Course, request_kind: str
) -> None:
    record_analytics_event(
        request,
        AnalyticsEvent.COURSE_ACCESS_REQUESTED,
        course_event_params(course) | {"request_kind": request_kind},
    )


def record_interest_expressed(request: HttpRequest, course: Course) -> None:
    _record_course_access_requested(request, course, "interest")


def record_application_submitted(request: HttpRequest, course: Course) -> None:
    _record_course_access_requested(request, course, "application")


def record_course_self_registered(request: HttpRequest, course: Course) -> None:
    record_analytics_event(
        request,
        AnalyticsEvent.COURSE_REGISTERED,
        course_event_params(course) | {"registration_method": "self_registration"},
    )


def _record_course_progress_event(
    request: HttpRequest,
    event: AnalyticsEvent,
    course: Course,
    via_cohort: bool,
) -> None:
    # registration_source is what keeps cohort learners visible in GA4: staff
    # register a cohort outside the learner's browser, so no course_registered
    # event is ever sent for them.
    registration_source = "cohort" if via_cohort else "individual"
    record_analytics_event(
        request,
        event,
        course_event_params(course) | {"registration_source": registration_source},
    )


def record_course_started(
    request: HttpRequest, course: Course, *, via_cohort: bool
) -> None:
    _record_course_progress_event(
        request, AnalyticsEvent.COURSE_STARTED, course, via_cohort
    )


def record_course_completed(
    request: HttpRequest, course: Course, *, via_cohort: bool
) -> None:
    _record_course_progress_event(
        request, AnalyticsEvent.COURSE_COMPLETED, course, via_cohort
    )
