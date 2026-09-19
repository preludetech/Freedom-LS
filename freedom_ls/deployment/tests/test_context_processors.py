import pytest

from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.template import engines
from django.test import Client, RequestFactory, override_settings
from django.urls import resolve, reverse
from django.utils.html import escapejs

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.deployment.context_processors import (
    analytics_enabled,
    google_analytics_config,
    posthog_config,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

_PENDING_SIGN_UP = {"name": "sign_up", "params": {"method": "email"}}
_SIGN_UP_SCRIPT = """gtag('event', 'sign_up', {"method": "email"})"""


def _request_with_session(path: str = "/") -> HttpRequest:
    request = RequestFactory().get(path)
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    return request


class TestPosthogConfig:
    @override_settings(POSTHOG_API_KEY="phc_test123")  # pragma: allowlist secret
    def test_returns_configured_key_and_a_host_when_key_set(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        result = posthog_config(request)

        assert result["posthog_api_key"] == "phc_test123"  # pragma: allowlist secret
        assert result["posthog_api_host"]

    @override_settings(POSTHOG_API_KEY=None)
    def test_returns_none_key_when_unset(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        result = posthog_config(request)

        assert result["posthog_api_key"] is None

    @override_settings(POSTHOG_API_HOST="https://override.example.test")
    def test_returns_overridden_api_host(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        result = posthog_config(request)

        assert result["posthog_api_host"] == "https://override.example.test"


class TestAnalyticsEnabled:
    def test_true_for_an_ordinary_url_name(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")
        request.resolver_match = resolve("/")

        result = analytics_enabled(request)

        assert result["analytics_enabled"] is True

    def test_false_for_account_confirm_email(self) -> None:
        factory = RequestFactory()
        path = reverse("account_confirm_email", args=["some-key"])
        request = factory.get(path)
        request.resolver_match = resolve(path)

        result = analytics_enabled(request)

        assert result["analytics_enabled"] is False

    def test_false_for_account_reset_password_from_key(self) -> None:
        factory = RequestFactory()
        path = reverse("account_reset_password_from_key", args=["some-uid", "some-key"])
        request = factory.get(path)
        request.resolver_match = resolve(path)

        result = analytics_enabled(request)

        assert result["analytics_enabled"] is False

    def test_true_when_resolver_match_is_none(self) -> None:
        factory = RequestFactory()
        request = factory.get("/some-unresolved-path/")

        result = analytics_enabled(request)

        assert result["analytics_enabled"] is True


@pytest.mark.django_db
class TestPosthogSnippetRendering:
    @override_settings(
        POSTHOG_API_KEY="phc_test",  # pragma: allowlist secret
        POSTHOG_API_HOST="https://example.test",
    )
    def test_snippet_renders_with_configured_key_and_host(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        assert "posthog.init(" in content
        assert "https://example.test" in content

    @override_settings(POSTHOG_API_KEY=None)
    def test_snippet_absent_when_key_unset(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        assert "posthog.init(" not in content

    @override_settings(
        POSTHOG_API_KEY="phc_test",  # pragma: allowlist secret
        POSTHOG_UI_HOST="https://ui.example.test",
    )
    def test_snippet_includes_ui_host_when_configured(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        assert "ui_host: 'https://ui.example.test'" in content

    @override_settings(POSTHOG_API_KEY="phc_test")  # pragma: allowlist secret
    def test_snippet_absent_on_a_token_bearing_page(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get(reverse("account_confirm_email", args=["some-key"]))

        content = response.content.decode()
        assert "posthog.init(" not in content


class TestGoogleAnalyticsConfig:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_returns_configured_measurement_id(self) -> None:
        request = _request_with_session()

        result = google_analytics_config(request)

        assert result["google_analytics_measurement_id"] == "G-TEST"

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_returns_none_when_unset(self) -> None:
        request = _request_with_session()

        result = google_analytics_config(request)

        assert result["google_analytics_measurement_id"] is None

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_drops_pending_events_when_unset(self) -> None:
        # Nothing will ever emit these, so they are discarded up front rather
        # than waiting in the session for a measurement ID that may never
        # arrive.
        request = _request_with_session()
        request.session["google_analytics_events"] = [_PENDING_SIGN_UP]

        google_analytics_config(request)

        assert "google_analytics_events" not in request.session


@pytest.mark.django_db
class TestGoogleAnalyticsSnippetRendering:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_loader_and_config_call_render_with_measurement_id_set(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        assert "googletagmanager.com/gtag/js?id=G-TEST" in content
        # The template escapes the ID for use inside a JS string literal, so a
        # hyphen in the ID (every real GA4 ID has one) is not literal here.
        assert f"gtag('config', '{escapejs('G-TEST')}'" in content

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_nothing_renders_with_measurement_id_unset(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        assert "googletagmanager.com" not in content

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_no_user_id_for_an_anonymous_request(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        assert "user_id" not in content

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_user_id_is_the_pk_for_a_logged_in_user(
        self, client: Client, mock_site_context: object
    ) -> None:
        user: User = UserFactory()
        client.force_login(user)

        response = client.get("/")

        content = response.content.decode()
        assert f"user_id: '{user.pk}'" in content
        script_start = content.index("gtag('config'")
        script_end = content.index("</script>", script_start)
        assert user.email not in content[script_start:script_end]

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_nothing_renders_on_a_token_bearing_page(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get(reverse("account_confirm_email", args=["some-key"]))

        content = response.content.decode()
        assert "googletagmanager.com" not in content


@pytest.fixture
def course_player_url_and_learner(mock_site_context: object) -> tuple[str, User]:
    """A course-player URL (extends `_base_interface.html`) and its registered learner."""
    course = CourseFactory(slug="ga-events-course")
    topic = TopicFactory(slug="ga-events-topic")
    course.items.create(child=topic, order=0)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "ga-events-course", "index": 1},
    )
    return url, user


@pytest.mark.django_db
class TestGoogleAnalyticsEventsPartial:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_event_recorded_in_session_renders_as_gtag_event(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get("/")

        content = response.content.decode()
        assert _SIGN_UP_SCRIPT in content

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_event_is_removed_from_session_after_rendering(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        client.get("/")

        assert "google_analytics_events" not in client.session

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_event_renders_once_on_a_page_that_extends_base_interface(
        self,
        client: Client,
        course_player_url_and_learner: tuple[str, User],
    ) -> None:
        url, user = course_player_url_and_learner
        client.force_login(user)
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get(url)

        content = response.content.decode()
        assert content.count(_SIGN_UP_SCRIPT) == 1

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_no_event_renders_when_measurement_id_unset(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get("/")

        content = response.content.decode()
        assert "gtag('event'" not in content

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_event_is_gone_from_session_when_measurement_id_unset(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        client.get("/")

        assert "google_analytics_events" not in client.session

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_nothing_renders_and_event_stays_on_a_token_bearing_page(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get(reverse("account_confirm_email", args=["some-key"]))

        content = response.content.decode()
        assert "gtag('event'" not in content
        assert client.session["google_analytics_events"] == [_PENDING_SIGN_UP]

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_boosted_request_keeps_the_event_inside_interface_main(
        self,
        client: Client,
        course_player_url_and_learner: tuple[str, User],
    ) -> None:
        url, user = course_player_url_and_learner
        client.force_login(user)
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get(url, HTTP_HX_REQUEST="true")

        content = response.content.decode()
        # Placement, not a full DOM parse: the event script must come after
        # the opening tag of #interface-main, the only region a boosted
        # course-player navigation keeps.
        assert content.index('id="interface-main"') < content.index(_SIGN_UP_SCRIPT)


@pytest.mark.django_db
class TestGoogleAnalyticsEventParameters:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_an_event_with_no_params_renders_an_empty_object(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [{"name": "sign_up", "params": {}}]
        session.save()

        response = client.get("/")

        assert "gtag('event', 'sign_up', {})" in response.content.decode()

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_a_value_that_would_close_the_script_element_is_escaped(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [
            {"name": "generate_lead", "params": {"lead_form": "</script><b>"}}
        ]
        session.save()

        response = client.get("/")

        content = response.content.decode()
        assert (
            """gtag('event', 'generate_lead', {"lead_form": """
            '"\\u003C/script\\u003E\\u003Cb\\u003E"})'
        ) in content


@pytest.mark.django_db
class TestGoogleAnalyticsConfigParamsBlock:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_a_template_filling_the_block_adds_to_the_config_call(
        self, mock_site_context: object
    ) -> None:
        landing_page = engines["django"].from_string(
            "{% extends '_base.html' %}"
            "{% block google_analytics_config_params %}"
            "content_group: 'landing_page'"
            "{% endblock %}"
        )

        content = landing_page.render(
            {"analytics_enabled": True}, _request_with_session()
        )

        assert (
            f"gtag('config', '{escapejs('G-TEST')}', {{ content_group: 'landing_page' }});"
            in content
        )

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_the_block_sits_beside_user_id_for_a_logged_in_user(
        self, mock_site_context: object
    ) -> None:
        user: User = UserFactory()
        request = _request_with_session()
        request.user = user
        landing_page = engines["django"].from_string(
            "{% extends '_base.html' %}"
            "{% block google_analytics_config_params %}"
            "content_group: 'landing_page'"
            "{% endblock %}"
        )

        content = landing_page.render({"analytics_enabled": True}, request)

        assert f"{{ user_id: '{user.pk}', content_group: 'landing_page' }}" in content
