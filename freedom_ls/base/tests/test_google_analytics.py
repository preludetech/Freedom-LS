from __future__ import annotations

import pytest

from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from freedom_ls.base.google_analytics import (
    GoogleAnalyticsEvent,
    pop_google_analytics_events,
    record_google_analytics_event,
    record_sign_up,
)


def _request_with_session() -> HttpRequest:
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    return request


class TestRecordGoogleAnalyticsEvent:
    def test_recording_stores_the_name_and_params(self) -> None:
        request = _request_with_session()

        record_google_analytics_event(
            request, GoogleAnalyticsEvent.SIGN_UP, {"method": "email"}
        )

        assert request.session["google_analytics_events"] == [
            {"name": "sign_up", "params": {"method": "email"}}
        ]

    def test_recording_without_params_stores_an_empty_params_dict(self) -> None:
        request = _request_with_session()

        record_google_analytics_event(request, GoogleAnalyticsEvent.SIGN_UP)

        assert request.session["google_analytics_events"] == [
            {"name": "sign_up", "params": {}}
        ]

    def test_recording_an_identical_event_twice_stores_it_once(self) -> None:
        request = _request_with_session()

        record_google_analytics_event(
            request, GoogleAnalyticsEvent.COURSE_STARTED, {"course_slug": "algebra"}
        )
        record_google_analytics_event(
            request, GoogleAnalyticsEvent.COURSE_STARTED, {"course_slug": "algebra"}
        )

        assert request.session["google_analytics_events"] == [
            {"name": "course_started", "params": {"course_slug": "algebra"}}
        ]

    def test_recording_the_same_event_for_two_courses_keeps_both(self) -> None:
        request = _request_with_session()

        record_google_analytics_event(
            request, GoogleAnalyticsEvent.COURSE_STARTED, {"course_slug": "algebra"}
        )
        record_google_analytics_event(
            request, GoogleAnalyticsEvent.COURSE_STARTED, {"course_slug": "botany"}
        )

        assert request.session["google_analytics_events"] == [
            {"name": "course_started", "params": {"course_slug": "algebra"}},
            {"name": "course_started", "params": {"course_slug": "botany"}},
        ]

    def test_an_event_name_fls_does_not_define_is_accepted(self) -> None:
        request = _request_with_session()

        record_google_analytics_event(
            request, "brochure_requested", {"lead_form": "brochure_request"}
        )

        assert request.session["google_analytics_events"] == [
            {"name": "brochure_requested", "params": {"lead_form": "brochure_request"}}
        ]

    def test_a_value_longer_than_100_characters_is_cut_to_100(self) -> None:
        request = _request_with_session()

        record_google_analytics_event(
            request, GoogleAnalyticsEvent.COURSE_STARTED, {"course_slug": "a" * 101}
        )

        stored = request.session["google_analytics_events"][0]["params"]["course_slug"]
        assert stored == "a" * 100

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "1st_event",
            "has-hyphen",
            "has space",
            "a" * 41,
            "_leading_underscore",
            "ga_custom",
            "google_custom",
            "firebase_custom",
        ],
    )
    def test_an_event_name_google_would_reject_raises(self, name: str) -> None:
        request = _request_with_session()

        with pytest.raises(ValueError, match="event name"):
            record_google_analytics_event(request, name)

    @pytest.mark.parametrize(
        "param_name",
        ["", "9lives", "has-hyphen", "a" * 41, "ga_param", "user_id", "currency"],
    )
    def test_a_parameter_name_google_would_reject_raises(self, param_name: str) -> None:
        request = _request_with_session()

        with pytest.raises(ValueError, match="parameter name"):
            record_google_analytics_event(
                request, GoogleAnalyticsEvent.SIGN_UP, {param_name: "x"}
            )

    def test_a_rejected_event_stores_nothing(self) -> None:
        request = _request_with_session()

        with pytest.raises(ValueError, match="event name"):
            record_google_analytics_event(request, "has-hyphen")

        assert "google_analytics_events" not in request.session


class TestPopGoogleAnalyticsEvents:
    def test_popping_returns_the_recorded_events(self) -> None:
        request = _request_with_session()
        record_google_analytics_event(
            request, GoogleAnalyticsEvent.GENERATE_LEAD, {"lead_form": "call_me_back"}
        )

        result = pop_google_analytics_events(request)

        assert result == [
            {"name": "generate_lead", "params": {"lead_form": "call_me_back"}}
        ]

    def test_popping_empties_the_session(self) -> None:
        request = _request_with_session()
        record_google_analytics_event(request, GoogleAnalyticsEvent.SIGN_UP)

        pop_google_analytics_events(request)

        assert "google_analytics_events" not in request.session

    def test_popping_with_nothing_recorded_returns_an_empty_list(self) -> None:
        request = _request_with_session()

        result = pop_google_analytics_events(request)

        assert result == []

    def test_popping_a_request_with_no_session_returns_an_empty_list(self) -> None:
        # A bare RequestFactory request never passed through SessionMiddleware,
        # as the context processor may see in a template unit test.
        request = RequestFactory().get("/")

        result = pop_google_analytics_events(request)

        assert result == []


class TestRecordSignUp:
    def test_records_sign_up_with_email_as_the_default_method(self) -> None:
        request = _request_with_session()

        record_sign_up(request)

        assert request.session["google_analytics_events"] == [
            {"name": "sign_up", "params": {"method": "email"}}
        ]
