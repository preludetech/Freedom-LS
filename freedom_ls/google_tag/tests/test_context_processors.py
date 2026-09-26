import pytest

from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.template import engines
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils.html import escapejs

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.google_tag.context_processors import google_tag_config
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

_PENDING_SIGN_UP = {"name": "sign_up", "params": {"method": "email"}}
_SIGN_UP_SCRIPT = """gtag('event', 'sign_up', {"method": "email"})"""
_SIGN_UP_CONVERSION_SCRIPT = (
    f"{_SIGN_UP_SCRIPT}; gtag('event', 'conversion', "
    f"{{send_to: '{escapejs('AW-TEST/QAsignup')}'}});"
)


def _request_with_session(path: str = "/") -> HttpRequest:
    request = RequestFactory().get(path)
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    return request


class TestGoogleTagConfig:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_returns_configured_measurement_id(self) -> None:
        request = _request_with_session()

        result = google_tag_config(request)

        assert result["google_analytics_measurement_id"] == "G-TEST"

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_returns_none_when_unset(self) -> None:
        request = _request_with_session()

        result = google_tag_config(request)

        assert result["google_analytics_measurement_id"] is None

    @override_settings(GOOGLE_ADS_CONVERSION_ID="AW-TEST")
    def test_returns_configured_google_ads_conversion_id(self) -> None:
        request = _request_with_session()

        result = google_tag_config(request)

        assert result["google_ads_conversion_id"] == "AW-TEST"

    @override_settings(GOOGLE_ADS_CONVERSION_ID=None)
    def test_returns_none_google_ads_conversion_id_when_unset(self) -> None:
        request = _request_with_session()

        result = google_tag_config(request)

        assert result["google_ads_conversion_id"] is None


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


@pytest.mark.django_db
class TestGoogleAdsSnippetRendering:
    @override_settings(
        GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST", GOOGLE_ADS_CONVERSION_ID="AW-TEST"
    )
    def test_ads_config_call_renders_after_the_analytics_one(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        analytics_config = content.index(f"gtag('config', '{escapejs('G-TEST')}'")
        ads_config = content.index(f"gtag('config', '{escapejs('AW-TEST')}');")
        assert analytics_config < ads_config

    @override_settings(
        GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST", GOOGLE_ADS_CONVERSION_ID=None
    )
    def test_no_ads_config_call_when_conversion_id_unset(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        assert "AW-" not in content
        assert "gtag('config'" in content

    @override_settings(
        GOOGLE_ANALYTICS_MEASUREMENT_ID=None, GOOGLE_ADS_CONVERSION_ID="AW-TEST"
    )
    def test_nothing_renders_without_a_measurement_id(
        self, client: Client, mock_site_context: object
    ) -> None:
        # The Ads tag rides on the GA4 loader; alone it loads nothing.
        response = client.get("/")

        content = response.content.decode()
        assert "googletagmanager.com" not in content
        assert "AW-" not in content

    @override_settings(
        GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST", GOOGLE_ADS_CONVERSION_ID="AW-TEST"
    )
    def test_nothing_renders_on_a_token_bearing_page(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get(reverse("account_confirm_email", args=["some-key"]))

        content = response.content.decode()
        assert "AW-" not in content


class TestConsentModeDeniedRegions:
    # The codes themselves are EU_CONSENT_POLICY_COUNTRIES's own contract,
    # covered by TestEuConsentPolicyCountries in base/tests/test_analytics_events.py.
    def test_context_value_is_a_list(self) -> None:
        request = _request_with_session()

        regions = google_tag_config(request)["consent_mode_denied_regions"]

        assert isinstance(regions, list)


@pytest.mark.django_db
class TestConsentModeDefaultRendering:
    @override_settings(
        GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST", GOOGLE_ADS_CONVERSION_ID="AW-TEST"
    )
    def test_consent_default_renders_before_either_config_call(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        consent_default = content.index("gtag('consent', 'default', {")
        assert consent_default < content.index("gtag('config'")

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_consent_default_denies_every_storage_type_for_the_listed_regions(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        start = content.index("gtag('consent', 'default', {")
        consent_call = content[start : content.index(");", start)]
        for storage in (
            "ad_storage",
            "ad_user_data",
            "ad_personalization",
            "analytics_storage",
        ):
            assert f"{storage}: 'denied'" in consent_call
        assert '"DE"' in consent_call
        assert '"ZA"' not in consent_call

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_nothing_renders_with_measurement_id_unset(
        self, client: Client, mock_site_context: object
    ) -> None:
        response = client.get("/")

        content = response.content.decode()
        assert "gtag('consent'" not in content


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
class TestGtagEventsPartial:
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


_ADS_SETTINGS = {
    "GOOGLE_ANALYTICS_MEASUREMENT_ID": "G-TEST",
    "GOOGLE_ADS_CONVERSION_ID": "AW-TEST",
    "GOOGLE_ADS_CONVERSION_LABELS": {"sign_up": "QAsignup"},
}


@pytest.mark.django_db
class TestGoogleAdsConversionRendering:
    @override_settings(**_ADS_SETTINGS)
    def test_a_mapped_event_sends_the_conversion_in_the_same_script(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get("/")

        assert _SIGN_UP_CONVERSION_SCRIPT in response.content.decode()

    @override_settings(**_ADS_SETTINGS)
    def test_an_unmapped_event_sends_no_conversion(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [
            {"name": "course_started", "params": {"course_slug": "algebra"}}
        ]
        session.save()

        response = client.get("/")

        content = response.content.decode()
        assert (
            """gtag('event', 'course_started', {"course_slug": "algebra"})""" in content
        )
        assert "'conversion'" not in content

    @override_settings(**{**_ADS_SETTINGS, "GOOGLE_ADS_CONVERSION_ID": None})
    def test_a_label_without_a_conversion_id_sends_no_conversion(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get("/")

        content = response.content.decode()
        assert _SIGN_UP_SCRIPT in content
        assert "'conversion'" not in content

    @override_settings(**_ADS_SETTINGS)
    def test_the_conversion_renders_once_on_a_page_that_extends_base_interface(
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

        assert response.content.decode().count(_SIGN_UP_CONVERSION_SCRIPT) == 1

    @override_settings(**_ADS_SETTINGS)
    def test_a_boosted_request_keeps_the_conversion_inside_interface_main(
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
        assert content.index('id="interface-main"') < content.index(
            _SIGN_UP_CONVERSION_SCRIPT
        )

    @override_settings(
        **{**_ADS_SETTINGS, "GOOGLE_ADS_CONVERSION_LABELS": {"sign_up": "</script><b>"}}
    )
    def test_a_label_that_would_close_the_script_element_is_escaped(
        self, client: Client, mock_site_context: object
    ) -> None:
        session = client.session
        session["google_analytics_events"] = [_PENDING_SIGN_UP]
        session.save()

        response = client.get("/")

        content = response.content.decode()
        assert "</script><b>" not in content[content.index("gtag('event'") :]
        assert f"send_to: '{escapejs('AW-TEST/</script><b>')}'" in content


@pytest.mark.django_db
class TestGtagEventParameters:
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
class TestGoogleAnalyticsContentGroup:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_a_page_passing_a_content_group_adds_it_to_the_config_call(
        self, mock_site_context: object
    ) -> None:
        landing_page = engines["django"].from_string(
            "{% extends '_base.html' %}"
            "{% block google_analytics %}"
            "{% include 'partials/google_analytics.html' "
            "with content_group='landing_page' %}"
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
    def test_the_content_group_sits_beside_user_id_for_a_logged_in_user(
        self, mock_site_context: object
    ) -> None:
        user: User = UserFactory()
        request = _request_with_session()
        request.user = user
        landing_page = engines["django"].from_string(
            "{% extends '_base.html' %}"
            "{% block google_analytics %}"
            "{% include 'partials/google_analytics.html' "
            "with content_group='landing_page' %}"
            "{% endblock %}"
        )

        content = landing_page.render({"analytics_enabled": True}, request)

        assert f"{{ user_id: '{user.pk}', content_group: 'landing_page' }}" in content
