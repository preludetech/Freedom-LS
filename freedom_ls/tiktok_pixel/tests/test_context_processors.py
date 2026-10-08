from __future__ import annotations

import pytest

from django.test import Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils.html import escapejs

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.tiktok_pixel.context_processors import tiktok_pixel_config

_VISITOR_COUNTRY_SETTINGS = {
    "TIKTOK_PIXEL_ID": "123",
    "VISITOR_COUNTRY_HEADER": "X-Visitor-Country",
}


class TestTikTokPixelConfig:
    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_returns_the_configured_id_where_ad_pixels_are_allowed(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert tiktok_pixel_config(request)["tiktok_pixel_id"] == "123"

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_returns_none_where_ad_pixels_are_refused(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="DE")

        assert tiktok_pixel_config(request)["tiktok_pixel_id"] is None

    @override_settings(TIKTOK_PIXEL_ID=None, VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_returns_none_with_the_id_unset(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert tiktok_pixel_config(request)["tiktok_pixel_id"] is None


@pytest.mark.django_db
class TestTikTokPixelSnippetRendering:
    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_loader_and_load_call_render_for_a_south_african_visitor(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert "analytics.tiktok.com/i18n/pixel/events.js" in content
        assert f"ttq.load('{escapejs('123')}');" in content

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_nothing_renders_for_a_german_visitor(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/", HTTP_X_VISITOR_COUNTRY="DE")

        assert "analytics.tiktok.com" not in response.content.decode()

    @override_settings(TIKTOK_PIXEL_ID=None, VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_nothing_renders_with_the_id_unset(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert "analytics.tiktok.com" not in response.content.decode()


@pytest.fixture
def course_player_url_and_learner(mock_site_context: object) -> tuple[str, User]:
    """A course-player URL (extends `_base_interface.html`) and its registered learner."""
    course = CourseFactory(slug="tiktok-events-course")
    topic = TopicFactory(slug="tiktok-events-topic")
    course.items.create(child=topic, order=0)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "tiktok-events-course", "index": 1},
    )
    return url, user


def _queue_events(client: Client, events: list[dict[str, object]]) -> None:
    session = client.session
    session["google_analytics_events"] = events
    session.save()


@pytest.mark.django_db
class TestTikTokPixelEventsPartial:
    @pytest.mark.parametrize(
        ("name", "params", "expected_call"),
        [
            (
                "course_registered",
                {"course_slug": "algebra"},
                """ttq.track('CompleteRegistration', {"course_slug": "algebra"}); """,
            ),
            (
                "course_access_requested",
                {"request_kind": "application"},
                """ttq.track('SubmitApplication', {"request_kind": "application"}); """,
            ),
            (
                "generate_lead",
                {"lead_form": "call_me_back"},
                """ttq.track('SubmitForm', {"lead_form": "call_me_back"}); """,
            ),
            (
                "sign_up",
                {"method": "email"},
                """ttq.track('SignUp', {"method": "email"}); """,
            ),
            (
                "course_completed",
                {"course_slug": "algebra"},
                """ttq.track('CourseCompleted', {"course_slug": "algebra"}); """,
            ),
        ],
    )
    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_a_mapped_event_renders_its_tiktok_call(
        self,
        client: Client,
        mock_site_context: object,
        name: str,
        params: dict[str, str],
        expected_call: str,
    ) -> None:
        _queue_events(client, [{"name": name, "params": params}])

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert (
            expected_call + "document.currentScript.remove();"
            in response.content.decode()
        )

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_an_interest_registration_renders_no_tiktok_call(
        self, client: Client, mock_site_context: object
    ) -> None:
        _queue_events(
            client,
            [
                {
                    "name": "course_access_requested",
                    "params": {"request_kind": "interest"},
                }
            ],
        )

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert "SubmitApplication" not in response.content.decode()

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_a_parameter_value_that_would_close_the_script_element_is_escaped(
        self, client: Client, mock_site_context: object
    ) -> None:
        _queue_events(
            client,
            [{"name": "generate_lead", "params": {"lead_form": "</script><b>"}}],
        )

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert (
            """ttq.track('SubmitForm', {"lead_form": """
            '"\\u003C/script\\u003E\\u003Cb\\u003E"});'
        ) in content

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_the_event_renders_once_on_a_page_that_extends_base_interface(
        self,
        client: Client,
        course_player_url_and_learner: tuple[str, User],
    ) -> None:
        url, user = course_player_url_and_learner
        client.force_login(user)
        _queue_events(client, [{"name": "sign_up", "params": {"method": "email"}}])

        response = client.get(url, HTTP_X_VISITOR_COUNTRY="ZA")

        assert response.content.decode().count("ttq.track('SignUp'") == 1
