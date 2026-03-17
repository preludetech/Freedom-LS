import pytest
from jinja2 import UndefinedError
from jinja2.sandbox import SecurityError

from django.contrib.sites.models import Site

from freedom_ls.webhooks.factories import WebhookEventFactory, WebhookSecretFactory
from freedom_ls.webhooks.rendering import (
    build_template_context,
    render_template,
)


@pytest.mark.django_db
class TestBuildTemplateContext:
    def test_includes_event_data(self, mock_site_context: Site) -> None:
        event = WebhookEventFactory(
            event_type="user.registered",
            payload={"user_id": "abc-123", "user_email": "test@example.com"},
        )
        context = build_template_context(event, mock_site_context.pk)
        event_ctx = context["event"]
        assert isinstance(event_ctx, dict)
        assert event_ctx["id"] == str(event.pk)
        assert event_ctx["type"] == "user.registered"
        data = event_ctx["data"]
        assert isinstance(data, dict)
        assert data["user_id"] == "abc-123"
        assert "timestamp" in event_ctx

    def test_includes_secrets(self, mock_site_context: Site) -> None:
        WebhookSecretFactory(
            name="api_key",
            encrypted_value="secret-value-123",  # pragma: allowlist secret
        )
        event = WebhookEventFactory()
        context = build_template_context(event, mock_site_context.pk)
        secrets_ctx = context["secrets"]
        assert isinstance(secrets_ctx, dict)
        assert secrets_ctx["api_key"] == "secret-value-123"  # pragma: allowlist secret

    def test_timestamp_format_uses_z_suffix(self, mock_site_context: Site) -> None:
        event = WebhookEventFactory()
        context = build_template_context(event, mock_site_context.pk)
        event_ctx = context["event"]
        assert isinstance(event_ctx, dict)
        timestamp = event_ctx["timestamp"]
        assert isinstance(timestamp, str)
        assert timestamp.endswith("Z")

    def test_empty_secrets_when_none_exist(self, mock_site_context: Site) -> None:
        event = WebhookEventFactory()
        context = build_template_context(event, mock_site_context.pk)
        assert context["secrets"] == {}


class TestRenderTemplate:
    def test_renders_variables_correctly(self) -> None:
        template_str = "Hello {{ name }}!"
        result = render_template(template_str, {"name": "World"})
        assert result == "Hello World!"

    def test_raises_on_undefined_variables(self) -> None:
        template_str = "Hello {{ undefined_var }}!"
        with pytest.raises(UndefinedError):
            render_template(template_str, {})

    def test_blocks_access_to_python_internals(self) -> None:
        template_str = "{{ ''.__class__.__mro__[1].__subclasses__() }}"
        with pytest.raises(SecurityError):
            render_template(template_str, {})

    def test_tojson_filter_works(self) -> None:
        template_str = "{{ data | tojson }}"
        result = render_template(template_str, {"data": {"key": "value"}})
        assert '"key"' in result
        assert '"value"' in result

    def test_replace_filter_works(self) -> None:
        template_str = "{{ name | replace('.', '_') }}"
        result = render_template(template_str, {"name": "user.registered"})
        assert result == "user_registered"

    def test_renders_nested_event_data(self) -> None:
        template_str = (
            '{"type": "{{ event.type }}", "email": "{{ event.data.user_email }}"}'
        )
        context = {
            "event": {
                "type": "user.registered",
                "data": {"user_email": "test@example.com"},
            }
        }
        result = render_template(template_str, context)
        assert "user.registered" in result
        assert "test@example.com" in result
