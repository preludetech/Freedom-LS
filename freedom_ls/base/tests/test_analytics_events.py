from __future__ import annotations

import pytest

from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, modify_settings, override_settings
from django.urls import resolve

from freedom_ls.base.analytics_events import (
    EU_CONSENT_POLICY_COUNTRIES,
    AnalyticsEvent,
    ad_pixels_allowed,
    pop_analytics_events,
    record_analytics_event,
    record_sign_up,
    visitor_country,
)


def _request_with_session() -> HttpRequest:
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    return request


class TestRecordAnalyticsEvent:
    def test_recording_stores_the_name_and_params(self) -> None:
        request = _request_with_session()

        record_analytics_event(request, AnalyticsEvent.SIGN_UP, {"method": "email"})

        assert request.session["analytics_events"] == [
            {"name": "sign_up", "params": {"method": "email"}}
        ]

    def test_recording_without_params_stores_an_empty_params_dict(self) -> None:
        request = _request_with_session()

        record_analytics_event(request, AnalyticsEvent.SIGN_UP)

        assert request.session["analytics_events"] == [
            {"name": "sign_up", "params": {}}
        ]

    def test_recording_an_identical_event_twice_stores_it_once(self) -> None:
        request = _request_with_session()

        record_analytics_event(
            request, AnalyticsEvent.COURSE_STARTED, {"course_slug": "algebra"}
        )
        record_analytics_event(
            request, AnalyticsEvent.COURSE_STARTED, {"course_slug": "algebra"}
        )

        assert request.session["analytics_events"] == [
            {"name": "course_started", "params": {"course_slug": "algebra"}}
        ]

    def test_recording_the_same_event_for_two_courses_keeps_both(self) -> None:
        request = _request_with_session()

        record_analytics_event(
            request, AnalyticsEvent.COURSE_STARTED, {"course_slug": "algebra"}
        )
        record_analytics_event(
            request, AnalyticsEvent.COURSE_STARTED, {"course_slug": "botany"}
        )

        assert request.session["analytics_events"] == [
            {"name": "course_started", "params": {"course_slug": "algebra"}},
            {"name": "course_started", "params": {"course_slug": "botany"}},
        ]

    def test_an_event_name_fls_does_not_define_is_accepted(self) -> None:
        request = _request_with_session()

        record_analytics_event(
            request, "brochure_requested", {"lead_form": "brochure_request"}
        )

        assert request.session["analytics_events"] == [
            {"name": "brochure_requested", "params": {"lead_form": "brochure_request"}}
        ]

    def test_a_value_longer_than_100_characters_is_cut_to_100(self) -> None:
        request = _request_with_session()

        record_analytics_event(
            request, AnalyticsEvent.COURSE_STARTED, {"course_slug": "a" * 101}
        )

        stored = request.session["analytics_events"][0]["params"]["course_slug"]
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
            record_analytics_event(request, name)

    @pytest.mark.parametrize(
        "param_name",
        ["", "9lives", "has-hyphen", "a" * 41, "ga_param", "user_id", "currency"],
    )
    def test_a_parameter_name_google_would_reject_raises(self, param_name: str) -> None:
        request = _request_with_session()

        with pytest.raises(ValueError, match="parameter name"):
            record_analytics_event(request, AnalyticsEvent.SIGN_UP, {param_name: "x"})

    def test_a_rejected_event_stores_nothing(self) -> None:
        request = _request_with_session()

        with pytest.raises(ValueError, match="event name"):
            record_analytics_event(request, "has-hyphen")

        assert "analytics_events" not in request.session


class TestPopAnalyticsEvents:
    def test_popping_returns_the_recorded_events(self) -> None:
        request = _request_with_session()
        record_analytics_event(
            request, AnalyticsEvent.GENERATE_LEAD, {"lead_form": "call_me_back"}
        )

        result = pop_analytics_events(request)

        assert result == [
            {"name": "generate_lead", "params": {"lead_form": "call_me_back"}}
        ]

    def test_popping_empties_the_session(self) -> None:
        request = _request_with_session()
        record_analytics_event(request, AnalyticsEvent.SIGN_UP)

        pop_analytics_events(request)

        assert "analytics_events" not in request.session

    def test_popping_with_nothing_recorded_returns_an_empty_list(self) -> None:
        request = _request_with_session()

        result = pop_analytics_events(request)

        assert result == []

    def test_popping_a_request_with_no_session_returns_an_empty_list(self) -> None:
        # A bare RequestFactory request never passed through SessionMiddleware,
        # as the context processor may see in a template unit test.
        request = RequestFactory().get("/")

        result = pop_analytics_events(request)

        assert result == []


class TestRecordSignUp:
    def test_records_sign_up_with_email_as_the_default_method(self) -> None:
        request = _request_with_session()

        record_sign_up(request)

        assert request.session["analytics_events"] == [
            {"name": "sign_up", "params": {"method": "email"}}
        ]


class TestRecordingWithNoPlatformAppInstalled:
    @modify_settings(
        INSTALLED_APPS={
            "remove": [
                "freedom_ls.google_tag",
                "freedom_ls.meta_pixel",
                "freedom_ls.tiktok_pixel",
            ]
        }
    )
    def test_records_nothing_when_no_context_processor_could_pop_it(self) -> None:
        request = _request_with_session()

        record_analytics_event(request, AnalyticsEvent.SIGN_UP)

        assert "analytics_events" not in request.session


class TestRecordingWithOnlyMetaPixelInstalled:
    @modify_settings(INSTALLED_APPS={"remove": ["freedom_ls.google_tag"]})
    def test_records_when_only_meta_pixel_can_pop_it(self) -> None:
        request = _request_with_session()

        record_sign_up(request)

        assert request.session["analytics_events"] == [
            {"name": "sign_up", "params": {"method": "email"}}
        ]


class TestVisitorCountry:
    @pytest.mark.parametrize(
        ("header_value", "expected"),
        [
            ("ZA", "ZA"),
            ("za", "ZA"),
            ("XX", None),
            ("T1", None),
            ("", None),
            ("ZAF", None),
        ],
    )
    @override_settings(VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_returns_the_expected_country_for_the_header_value(
        self, header_value: str, expected: str | None
    ) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY=header_value)

        assert visitor_country(request) == expected

    @override_settings(VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_a_missing_header_gives_none(self) -> None:
        request = RequestFactory().get("/")

        assert visitor_country(request) is None

    @override_settings(VISITOR_COUNTRY_HEADER=None)
    def test_an_unset_setting_gives_none(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert visitor_country(request) is None


class TestAdPixelsAllowed:
    @override_settings(VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_a_south_african_visitor_is_allowed(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert ad_pixels_allowed(request) is True

    @pytest.mark.parametrize("country", ["DE", "GB", "CH", "NO"])
    @override_settings(VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_an_eu_consent_policy_country_is_refused(self, country: str) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY=country)

        assert ad_pixels_allowed(request) is False

    @override_settings(VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_an_unknown_country_is_refused(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="XX")

        assert ad_pixels_allowed(request) is False

    @override_settings(VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_an_educator_interface_page_is_refused_even_for_south_africa(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="ZA")
        request.resolver_match = resolve("/educator/organisations/some-org/cohorts")

        assert ad_pixels_allowed(request) is False


class TestEuConsentPolicyCountries:
    def test_has_32_unique_codes(self) -> None:
        assert len(EU_CONSENT_POLICY_COUNTRIES) == 32
        assert len(set(EU_CONSENT_POLICY_COUNTRIES)) == 32

    @pytest.mark.parametrize("code", EU_CONSENT_POLICY_COUNTRIES)
    def test_each_code_is_two_upper_case_letters(self, code: str) -> None:
        assert len(code) == 2
        assert code.isalpha()
        assert code.isupper()

    def test_uses_gb_not_uk(self) -> None:
        assert "GB" in EU_CONSENT_POLICY_COUNTRIES
        assert "UK" not in EU_CONSENT_POLICY_COUNTRIES

    def test_uses_gr_not_el(self) -> None:
        assert "GR" in EU_CONSENT_POLICY_COUNTRIES
        assert "EL" not in EU_CONSENT_POLICY_COUNTRIES

    def test_leaves_south_africa_out(self) -> None:
        assert "ZA" not in EU_CONSENT_POLICY_COUNTRIES
