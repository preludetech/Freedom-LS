import pytest

from django.test import Client, RequestFactory, override_settings

from freedom_ls.deployment.context_processors import posthog_config


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
