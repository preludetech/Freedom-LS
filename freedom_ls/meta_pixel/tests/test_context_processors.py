from __future__ import annotations

import pytest

from django.test import Client, RequestFactory, override_settings
from django.urls import resolve, reverse
from django.utils.html import escapejs

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.meta_pixel.context_processors import meta_pixel_config
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

_VISITOR_COUNTRY_SETTINGS = {
    "META_PIXEL_ID": "123",
    "VISITOR_COUNTRY_HEADER": "X-Visitor-Country",
}


class TestMetaPixelConfig:
    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_returns_the_configured_id_for_a_south_african_visitor(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert meta_pixel_config(request)["meta_pixel_id"] == "123"

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_returns_none_for_an_eu_consent_policy_country(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="DE")

        assert meta_pixel_config(request)["meta_pixel_id"] is None

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_returns_none_for_an_unknown_country(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="XX")

        assert meta_pixel_config(request)["meta_pixel_id"] is None

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_returns_none_on_an_educator_interface_page(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="ZA")
        request.resolver_match = resolve("/educator/organisations/some-org/cohorts")

        assert meta_pixel_config(request)["meta_pixel_id"] is None

    @override_settings(META_PIXEL_ID=None, VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_returns_none_with_the_id_unset(self) -> None:
        request = RequestFactory().get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert meta_pixel_config(request)["meta_pixel_id"] is None


@pytest.mark.django_db
class TestMetaPixelSnippetRendering:
    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_loader_and_init_call_render_for_a_south_african_visitor(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert "connect.facebook.net/en_US/fbevents.js" in content
        assert f"fbq('init', '{escapejs('123')}');" in content

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_autoconfig_call_renders_before_init_call(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert content.index("fbq('set', 'autoConfig'") < content.index("fbq('init'")

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_nothing_renders_for_a_german_visitor(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/", HTTP_X_VISITOR_COUNTRY="DE")

        assert "connect.facebook.net" not in response.content.decode()

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_nothing_renders_without_the_header(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        assert "connect.facebook.net" not in response.content.decode()

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_nothing_renders_on_an_educator_page(
        self, client: Client, mock_site_context: object
    ) -> None:
        organisation = OrganisationFactory()
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_staff")
        client.force_login(educator)
        url = reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )

        response = client.get(url, HTTP_X_VISITOR_COUNTRY="ZA")

        assert "connect.facebook.net" not in response.content.decode()

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_nothing_renders_on_account_confirm_email(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get(
            reverse("account_confirm_email", args=["some-key"]),
            HTTP_X_VISITOR_COUNTRY="ZA",
        )

        assert "connect.facebook.net" not in response.content.decode()

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_nothing_renders_on_account_reset_password_from_key(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get(
            reverse("account_reset_password_from_key", args=["some-uid", "some-key"]),
            HTTP_X_VISITOR_COUNTRY="ZA",
        )

        assert "connect.facebook.net" not in response.content.decode()

    @override_settings(META_PIXEL_ID=None, VISITOR_COUNTRY_HEADER="X-Visitor-Country")
    def test_nothing_renders_with_the_id_unset(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert "connect.facebook.net" not in response.content.decode()


@pytest.fixture
def course_player_url_and_learner(mock_site_context: object) -> tuple[str, User]:
    """A course-player URL (extends `_base_interface.html`) and its registered learner."""
    course = CourseFactory(slug="meta-events-course")
    topic = TopicFactory(slug="meta-events-topic")
    course.items.create(child=topic, order=0)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "meta-events-course", "index": 1},
    )
    return url, user


@pytest.mark.django_db
class TestMetaPixelEventsPartial:
    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_course_registered_renders_complete_registration(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [
            {
                "name": "course_registered",
                "params": {"course_slug": "algebra"},
            }
        ]
        session.save()

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert (
            """fbq('track', 'CompleteRegistration', {"course_slug": "algebra"}); """
            "document.currentScript.remove();" in content
        )

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_application_submitted_renders_submit_application(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [
            {
                "name": "course_access_requested",
                "params": {"request_kind": "application"},
            }
        ]
        session.save()

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert (
            """fbq('track', 'SubmitApplication', {"request_kind": """
            """"application"}); document.currentScript.remove();""" in content
        )

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_generate_lead_renders_lead(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [
            {"name": "generate_lead", "params": {"lead_form": "call_me_back"}}
        ]
        session.save()

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert (
            """fbq('track', 'Lead', {"lead_form": "call_me_back"}); """
            "document.currentScript.remove();" in content
        )

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_sign_up_renders_track_custom_sign_up(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [
            {"name": "sign_up", "params": {"method": "email"}}
        ]
        session.save()

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert (
            """fbq('trackCustom', 'SignUp', {"method": "email"}); """
            "document.currentScript.remove();" in content
        )

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_course_completed_renders_track_custom_course_completed(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [
            {
                "name": "course_completed",
                "params": {"course_slug": "algebra"},
            }
        ]
        session.save()

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert (
            """fbq('trackCustom', 'CourseCompleted', {"course_slug": "algebra"}); """
            "document.currentScript.remove();" in content
        )

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_an_interest_registration_renders_no_meta_call(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [
            {
                "name": "course_access_requested",
                "params": {"request_kind": "interest"},
            }
        ]
        session.save()

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        assert "SubmitApplication" not in response.content.decode()

    @override_settings(**_VISITOR_COUNTRY_SETTINGS)
    def test_a_parameter_value_that_would_close_the_script_element_is_escaped(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["analytics_events"] = [
            {"name": "generate_lead", "params": {"lead_form": "</script><b>"}}
        ]
        session.save()

        response = client.get("/", HTTP_X_VISITOR_COUNTRY="ZA")

        content = response.content.decode()
        assert (
            """fbq('track', 'Lead', {"lead_form": """
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
        session = client.session
        session["analytics_events"] = [
            {"name": "sign_up", "params": {"method": "email"}}
        ]
        session.save()

        response = client.get(url, HTTP_X_VISITOR_COUNTRY="ZA")

        assert response.content.decode().count("fbq('trackCustom', 'SignUp'") == 1
