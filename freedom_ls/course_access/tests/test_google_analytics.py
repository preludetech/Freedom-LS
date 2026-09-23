from __future__ import annotations

from collections.abc import Callable

import pytest

from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.course_access.google_analytics import (
    course_event_params,
    record_application_submitted,
    record_course_completed,
    record_course_self_registered,
    record_course_started,
    record_interest_expressed,
)


def _request_with_session() -> HttpRequest:
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    return request


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("record", "name", "extra_params"),
    [
        (
            record_interest_expressed,
            "course_access_requested",
            {"request_kind": "interest"},
        ),
        (
            record_application_submitted,
            "course_access_requested",
            {"request_kind": "application"},
        ),
        (
            record_course_self_registered,
            "course_registered",
            {"registration_method": "self_registration"},
        ),
    ],
)
def test_course_event_is_recorded_with_its_course_params(
    mock_site_context,
    record: Callable[[HttpRequest, Course], None],
    name: str,
    extra_params: dict[str, str],
) -> None:
    course = CourseFactory()
    request = _request_with_session()

    record(request, course)

    assert request.session["google_analytics_events"] == [
        {"name": name, "params": course_event_params(course) | extra_params}
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("record", "name"),
    [
        (record_course_started, "course_started"),
        (record_course_completed, "course_completed"),
    ],
)
@pytest.mark.parametrize(
    ("via_cohort", "registration_source"),
    [(True, "cohort"), (False, "individual")],
)
def test_course_progress_event_names_the_registration_source(
    mock_site_context,
    record: Callable[..., None],
    name: str,
    via_cohort: bool,
    registration_source: str,
) -> None:
    course = CourseFactory()
    request = _request_with_session()

    record(request, course, via_cohort=via_cohort)

    assert request.session["google_analytics_events"] == [
        {
            "name": name,
            "params": course_event_params(course)
            | {"registration_source": registration_source},
        }
    ]
