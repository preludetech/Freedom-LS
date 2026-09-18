import pytest

from django.test import Client, RequestFactory, override_settings
from django.urls import resolve, reverse
from django.utils.html import escapejs

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.deployment.context_processors import (
    analytics_enabled,
    google_analytics_config,
    posthog_config,
)


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
        factory = RequestFactory()
        request = factory.get("/")

        result = google_analytics_config(request)

        assert result["google_analytics_measurement_id"] == "G-TEST"

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID=None)
    def test_returns_none_when_unset(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        result = google_analytics_config(request)

        assert result["google_analytics_measurement_id"] is None


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
