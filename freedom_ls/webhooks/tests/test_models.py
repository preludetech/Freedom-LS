from unittest.mock import patch

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from freedom_ls.webhooks.factories import (
    WebhookDeliveryFactory,
    WebhookEndpointFactory,
    WebhookSecretFactory,
)


@pytest.mark.django_db
class TestWebhookEndpoint:
    def test_secret_auto_generated_on_save(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        assert endpoint.secret
        # Secret should not change on subsequent saves
        original_secret = endpoint.secret
        endpoint.save()
        assert endpoint.secret == original_secret

    def test_clean_https_not_enforced_in_debug(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(url="http://example.com/webhook")
        # Should not raise
        endpoint.clean()

    def test_clean_http_url_allowed_in_production_for_public_ips(
        self, mock_site_context: object, settings: object, mocker: object
    ) -> None:
        """HTTP URLs are allowed for public IPs — SSRF check replaces the old HTTPS-only rule."""
        import socket

        settings.DEBUG = False
        mocker.patch(
            "freedom_ls.webhooks.models.socket.getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 80))
            ],
        )
        endpoint = WebhookEndpointFactory(url="http://example.com/webhook")
        # Should not raise — public IP with HTTP is allowed
        endpoint.clean()

    def test_secret_longer_than_64_chars_stored_without_truncation(
        self, mock_site_context: object
    ) -> None:
        """Issue #9: secrets up to 65 chars should be stored without truncation."""
        long_secret = "a" * 65
        with patch(
            "freedom_ls.webhooks.models.secrets.token_urlsafe", return_value=long_secret
        ):
            endpoint = WebhookEndpointFactory()
        endpoint.refresh_from_db()
        assert endpoint.secret == long_secret

    def test_clean_empty_event_types_passes(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(event_types=[])
        # Should not raise
        endpoint.clean()

    # --- Step 3a: has_transformation property ---

    def test_has_transformation_false_when_body_template_is_none(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(body_template="")
        assert endpoint.has_transformation is False

    def test_has_transformation_false_when_body_template_is_empty(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(body_template="")
        assert endpoint.has_transformation is False

    def test_has_transformation_true_when_body_template_is_set(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(body_template='{"key": "{{ event.type }}"}')
        assert endpoint.has_transformation is True

    def test_new_fields_default_to_empty(self, mock_site_context: object) -> None:
        """New transformation fields should default to empty without breaking existing endpoints."""
        endpoint = WebhookEndpointFactory()
        endpoint.refresh_from_db()
        assert endpoint.http_method == ""
        assert endpoint.content_type == ""
        assert endpoint.headers_template == ""
        assert endpoint.body_template == ""
        assert endpoint.auth_type == "signing"
        assert endpoint.preset_slug == ""

    # --- Step 3b: Validation ---

    def test_clean_transformation_fields_without_body_template_raises(
        self, mock_site_context: object, settings: object
    ) -> None:
        """If any transformation field is set but body_template is empty, raise ValidationError."""
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            http_method="POST",
            body_template="",
        )
        with pytest.raises(ValidationError, match="body_template"):
            endpoint.clean()

    def test_clean_transformation_fields_with_headers_but_no_body_raises(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            headers_template='{"X-Custom": "value"}',
            body_template="",
        )
        with pytest.raises(ValidationError, match="body_template"):
            endpoint.clean()

    def test_clean_valid_jinja2_syntax_passes(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            body_template='{"event": "{{ event.type }}"}',
        )
        # Should not raise
        endpoint.clean()

    def test_clean_invalid_jinja2_syntax_fails(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            body_template='{"event": "{{ event.type }"}',
        )
        with pytest.raises(ValidationError, match="body_template"):
            endpoint.clean()

    def test_clean_invalid_jinja2_syntax_in_headers_fails(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            body_template='{"event": "{{ event.type }}"}',
            headers_template='{"X-Custom": "{{ secrets.key }"}',
        )
        with pytest.raises(ValidationError, match="headers_template"):
            endpoint.clean()

    def test_clean_json_content_type_validates_rendered_output(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            content_type="application/json",
            body_template="this is not json {{ event.type }}",
        )
        with pytest.raises(ValidationError, match="body_template"):
            endpoint.clean()

    def test_clean_json_content_type_valid_json_passes(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            content_type="application/json",
            body_template='{"event": "{{ event.type }}"}',
        )
        # Should not raise
        endpoint.clean()

    def test_clean_headers_template_must_be_json_object(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            body_template='{"event": "{{ event.type }}"}',
            headers_template='"not an object"',
        )
        with pytest.raises(ValidationError, match="headers_template"):
            endpoint.clean()

    def test_clean_headers_template_valid_json_object_passes(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            body_template='{"event": "{{ event.type }}"}',
            headers_template='{"X-Custom": "value"}',
        )
        # Should not raise
        endpoint.clean()

    # --- Step 3b: SSRF protection ---

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/webhook",
            "http://127.0.0.1/webhook",
            "http://[::1]/webhook",
            "http://10.0.0.1/webhook",
            "http://172.16.0.1/webhook",
            "http://192.168.1.1/webhook",
            "http://169.254.169.254/webhook",
        ],
    )
    def test_clean_ssrf_private_ips_rejected_in_production(
        self, mock_site_context: object, settings: object, url: str, mocker: object
    ) -> None:
        settings.DEBUG = False
        # Mock getaddrinfo to return the IP from the URL for hostname resolution
        import ipaddress
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(url)
        hostname = parsed.hostname
        # For IP addresses, mock getaddrinfo to return the IP itself
        try:
            addr = ipaddress.ip_address(hostname)
            family = socket.AF_INET6 if addr.version == 6 else socket.AF_INET
            mocker.patch(
                "freedom_ls.webhooks.models.socket.getaddrinfo",
                return_value=[(family, socket.SOCK_STREAM, 0, "", (str(addr), 80))],
            )
        except ValueError:
            # hostname like "localhost"
            mocker.patch(
                "freedom_ls.webhooks.models.socket.getaddrinfo",
                return_value=[
                    (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 80))
                ],
            )

        endpoint = WebhookEndpointFactory(url=url)
        with pytest.raises(ValidationError, match="url"):
            endpoint.clean()

    def test_clean_ssrf_public_ip_allowed_in_production(
        self, mock_site_context: object, settings: object, mocker: object
    ) -> None:
        settings.DEBUG = False
        import socket

        mocker.patch(
            "freedom_ls.webhooks.models.socket.getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443))
            ],
        )
        endpoint = WebhookEndpointFactory(url="https://example.com/webhook")
        # Should not raise
        endpoint.clean()

    def test_clean_ssrf_skipped_in_debug_mode(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(url="http://localhost/webhook")
        # Should not raise — SSRF checks skipped in debug
        endpoint.clean()

    def test_clean_rejects_non_http_scheme(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = False
        endpoint = WebhookEndpointFactory(url="ftp://example.com/webhook")
        with pytest.raises(ValidationError, match="url"):
            endpoint.clean()


@pytest.mark.django_db
class TestWebhookSecret:
    def test_encrypted_value_stored_and_retrieved(
        self, mock_site_context: object
    ) -> None:
        """Encrypted value should be retrievable after save."""
        secret = WebhookSecretFactory(encrypted_value="my-secret-api-key")
        secret.refresh_from_db()
        assert secret.encrypted_value == "my-secret-api-key"

    @pytest.mark.parametrize(
        "invalid_name",
        ["123bad", "has-dash", "has space", "has.dot", ""],
    )
    def test_name_validation_rejects_invalid_names(
        self, mock_site_context: object, invalid_name: str
    ) -> None:
        """Names must match ^[a-zA-Z_][a-zA-Z0-9_]*$."""
        secret = WebhookSecretFactory(name=invalid_name)
        with pytest.raises(ValidationError):
            secret.full_clean()

    @pytest.mark.parametrize(
        "valid_name",
        ["brevo_api_key", "_private", "A", "myKey123", "UPPER_CASE"],
    )
    def test_name_validation_accepts_valid_names(
        self, mock_site_context: object, valid_name: str
    ) -> None:
        """Valid identifier-style names should pass validation."""
        secret = WebhookSecretFactory(name=valid_name)
        # Should not raise
        secret.full_clean()

    def test_unique_together_site_and_name(self, mock_site_context: object) -> None:
        """Two secrets with the same name on the same site should fail."""
        WebhookSecretFactory(name="duplicate_key")
        with pytest.raises(IntegrityError):
            WebhookSecretFactory(name="duplicate_key")


@pytest.mark.django_db
class TestWebhookDelivery:
    def test_short_response_body_not_truncated(self, mock_site_context: object) -> None:
        short_body = "x" * 100
        delivery = WebhookDeliveryFactory(last_response_body=short_body)
        assert delivery.last_response_body == short_body

    def test_delivery_linked_to_event_and_endpoint(
        self, mock_site_context: object
    ) -> None:
        delivery = WebhookDeliveryFactory()
        assert delivery.event is not None
        assert delivery.endpoint is not None
        assert delivery.event.deliveries.count() == 1
        assert delivery.endpoint.deliveries.count() == 1
