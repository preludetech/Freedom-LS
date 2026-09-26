from __future__ import annotations

import copy

import pytest
import pytest_django.fixtures

from django.test import Client, override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

_PENDING_SIGN_UP = {"name": "sign_up", "params": {"method": "email"}}
_SIGN_UP_SCRIPT = """gtag('event', 'sign_up', {"method": "email"})"""
_META_SIGN_UP_SCRIPT = """fbq('trackCustom', 'SignUp', {"method": "email"})"""
_TIKTOK_SIGN_UP_SCRIPT = """ttq.track('SignUp', {"method": "email"})"""

_ALL_PLATFORM_SETTINGS = {
    "GOOGLE_ANALYTICS_MEASUREMENT_ID": "G-TEST",
    "META_PIXEL_ID": "123",
    "TIKTOK_PIXEL_ID": "456",
    "VISITOR_COUNTRY_HEADER": "X-Visitor-Country",
}


@pytest.fixture
def course_player_url_and_learner(mock_site_context: object) -> tuple[str, User]:
    """A course-player URL (extends `_base_interface.html`) and its registered learner."""
    course = CourseFactory(slug="analytics-events-course")
    topic = TopicFactory(slug="analytics-events-topic")
    course.items.create(child=topic, order=0)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "analytics-events-course", "index": 1},
    )
    return url, user


@pytest.mark.django_db
class TestAnalyticsEventsPartial:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_a_recorded_event_is_gone_from_the_session_with_no_measurement_id(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        client.get("/")

        assert "analytics_events" not in client.session

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_a_recorded_event_stays_on_a_token_bearing_page(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get(reverse("account_confirm_email", args=["some-key"]))

        content = response.content.decode()
        assert "gtag('event'" not in content
        assert client.session["analytics_events"] == [_PENDING_SIGN_UP]

    @override_settings(**_ALL_PLATFORM_SETTINGS)
    def test_a_boosted_request_keeps_the_emitted_script_inside_interface_main(
        self,
        client: Client,
        course_player_url_and_learner: tuple[str, User],
    ) -> None:
        url, user = course_player_url_and_learner
        client.force_login(user)
        session = client.session
        session["analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get(url, HTTP_HX_REQUEST="true", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        # Placement, not a full DOM parse: the event script must come after
        # the opening tag of #interface-main, the only region a boosted
        # course-player navigation keeps.
        assert content.index('id="interface-main"') < content.index(_SIGN_UP_SCRIPT)
        assert content.index('id="interface-main"') < content.index(
            _META_SIGN_UP_SCRIPT
        )
        assert content.index('id="interface-main"') < content.index(
            _TIKTOK_SIGN_UP_SCRIPT
        )

    @override_settings(**_ALL_PLATFORM_SETTINGS)
    def test_one_recorded_event_renders_one_call_per_platform_from_the_same_pop(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert content.count(_SIGN_UP_SCRIPT) == 1
        assert content.count(_META_SIGN_UP_SCRIPT) == 1
        assert content.count(_TIKTOK_SIGN_UP_SCRIPT) == 1

    @override_settings(**_ALL_PLATFORM_SETTINGS)
    def test_the_express_interest_swap_carries_the_ga4_call_and_no_meta_call(
        self, client: Client, mock_site_context: object
    ) -> None:
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user: User = UserFactory()
        client.force_login(user)
        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )

        response = client.post(url, HTTP_HX_REQUEST="true", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert "gtag('event', 'course_access_requested'" in content
        assert "fbq(" not in content
        assert "ttq." not in content

    def test_pages_render_without_google_tag_installed(
        self,
        client: Client,
        settings: pytest_django.fixtures.SettingsWrapper,
        mock_site_context: object,
        course_player_url_and_learner: tuple[str, User],
    ) -> None:
        url, user = course_player_url_and_learner
        client.force_login(user)
        settings.INSTALLED_APPS = [
            app for app in settings.INSTALLED_APPS if app != "freedom_ls.google_tag"
        ]
        templates = copy.deepcopy(settings.TEMPLATES)
        templates[0]["OPTIONS"]["context_processors"] = [
            processor
            for processor in templates[0]["OPTIONS"]["context_processors"]
            if processor != "freedom_ls.google_tag.context_processors.google_tag_config"
        ]
        settings.TEMPLATES = templates

        home_response = client.get("/")
        player_response = client.get(url)

        assert home_response.status_code == 200
        assert player_response.status_code == 200
        assert "gtag(" not in home_response.content.decode()
        assert "gtag(" not in player_response.content.decode()

    @pytest.mark.parametrize(
        ("app_name", "context_processor", "absent_string", "other_scripts"),
        [
            (
                "freedom_ls.meta_pixel",
                "freedom_ls.meta_pixel.context_processors.meta_pixel_config",
                "fbq(",
                (_SIGN_UP_SCRIPT, _TIKTOK_SIGN_UP_SCRIPT),
            ),
            (
                "freedom_ls.tiktok_pixel",
                "freedom_ls.tiktok_pixel.context_processors.tiktok_pixel_config",
                "ttq.",
                (_SIGN_UP_SCRIPT, _META_SIGN_UP_SCRIPT),
            ),
        ],
    )
    @override_settings(**_ALL_PLATFORM_SETTINGS)
    def test_the_other_platforms_still_emit_with_one_platform_uninstalled(
        self,
        client: Client,
        settings: pytest_django.fixtures.SettingsWrapper,
        course_player_url_and_learner: tuple[str, User],
        app_name: str,
        context_processor: str,
        absent_string: str,
        other_scripts: tuple[str, str],
    ) -> None:
        url, user = course_player_url_and_learner
        client.force_login(user)
        session = client.session
        session["analytics_events"] = [_PENDING_SIGN_UP]
        session.save()
        settings.INSTALLED_APPS = [
            app for app in settings.INSTALLED_APPS if app != app_name
        ]
        templates = copy.deepcopy(settings.TEMPLATES)
        templates[0]["OPTIONS"]["context_processors"] = [
            processor
            for processor in templates[0]["OPTIONS"]["context_processors"]
            if processor != context_processor
        ]
        settings.TEMPLATES = templates

        response = client.get(url, HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert response.status_code == 200
        assert absent_string not in content
        for other_script in other_scripts:
            assert other_script in content
