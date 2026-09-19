from __future__ import annotations

from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from freedom_ls.base.google_analytics import (
    GoogleAnalyticsEvent,
    pop_google_analytics_flags,
    record_google_analytics_flag,
)


def _request_with_session() -> HttpRequest:
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    return request


class TestRecordGoogleAnalyticsFlag:
    def test_recording_stores_the_flag(self) -> None:
        request = _request_with_session()

        record_google_analytics_flag(request, GoogleAnalyticsEvent.SIGN_UP)

        assert request.session["google_analytics_flags"] == ["sign_up"]

    def test_recording_the_same_event_twice_stores_it_once(self) -> None:
        request = _request_with_session()

        record_google_analytics_flag(request, GoogleAnalyticsEvent.SIGN_UP)
        record_google_analytics_flag(request, GoogleAnalyticsEvent.SIGN_UP)

        assert request.session["google_analytics_flags"] == ["sign_up"]

    def test_recording_two_different_events_keeps_both(self) -> None:
        request = _request_with_session()

        record_google_analytics_flag(request, GoogleAnalyticsEvent.SIGN_UP)
        record_google_analytics_flag(request, GoogleAnalyticsEvent.TUTORIAL_BEGIN)

        assert request.session["google_analytics_flags"] == [
            "sign_up",
            "tutorial_begin",
        ]


class TestPopGoogleAnalyticsFlags:
    def test_popping_returns_the_recorded_flags(self) -> None:
        request = _request_with_session()
        record_google_analytics_flag(request, GoogleAnalyticsEvent.GENERATE_LEAD)

        result = pop_google_analytics_flags(request)

        assert result == ["generate_lead"]

    def test_popping_empties_the_session(self) -> None:
        request = _request_with_session()
        record_google_analytics_flag(request, GoogleAnalyticsEvent.GENERATE_LEAD)

        pop_google_analytics_flags(request)

        assert "google_analytics_flags" not in request.session

    def test_popping_with_nothing_recorded_returns_an_empty_list(self) -> None:
        request = _request_with_session()

        result = pop_google_analytics_flags(request)

        assert result == []

    def test_popping_a_request_with_no_session_returns_an_empty_list(self) -> None:
        # A bare RequestFactory request never passed through SessionMiddleware,
        # as the context processor may see in a template unit test.
        request = RequestFactory().get("/")

        result = pop_google_analytics_flags(request)

        assert result == []
