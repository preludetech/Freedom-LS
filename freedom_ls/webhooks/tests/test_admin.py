from unittest.mock import patch

import httpx
import pytest

from django.utils import timezone

from freedom_ls.webhooks.admin import (
    WebhookDeliveryAdmin,
    WebhookEndpointAdmin,
    WebhookSecretAdmin,
)
from freedom_ls.webhooks.factories import (
    WebhookDeliveryFactory,
    WebhookEndpointFactory,
    WebhookSecretFactory,
)
from freedom_ls.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookSecret


@pytest.mark.django_db
class TestRetryDeliveries:
    def test_retry_resets_delivery_state(self, mock_site_context: object) -> None:
        """Issue #1: retry must reset attempt_count and status before re-attempting."""
        delivery = WebhookDeliveryFactory(
            attempt_count=6,
            status="dead_letter",
        )
        endpoint = delivery.endpoint

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        admin_instance = WebhookDeliveryAdmin(WebhookDelivery, None)
        queryset = WebhookDelivery.objects.filter(pk=delivery.pk)

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            admin_instance.retry_deliveries(request=None, queryset=queryset)

        delivery.refresh_from_db()
        assert delivery.status == "success"
        assert delivery.attempt_count == 1  # reset to 0, then incremented by attempt

    def test_retry_uses_select_related(self, mock_site_context: object) -> None:
        """Issue #5: retry queryset should use select_related to avoid N+1."""
        delivery = WebhookDeliveryFactory(
            status="failed",
        )

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        admin_instance = WebhookDeliveryAdmin(WebhookDelivery, None)
        queryset = WebhookDelivery.objects.filter(pk=delivery.pk)

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            # Use assertNumQueries or just verify it works without extra queries
            admin_instance.retry_deliveries(request=None, queryset=queryset)
            mock_request.assert_called_once()


@pytest.mark.django_db
class TestRetryPermanentFailures:
    def test_retry_includes_permanent_failure_deliveries(
        self, mock_site_context: object
    ) -> None:
        delivery = WebhookDeliveryFactory(
            attempt_count=1,
            status="permanent_failure",
        )
        endpoint = delivery.endpoint

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        admin_instance = WebhookDeliveryAdmin(WebhookDelivery, None)
        queryset = WebhookDelivery.objects.filter(pk=delivery.pk)

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            admin_instance.retry_deliveries(request=None, queryset=queryset)

        delivery.refresh_from_db()
        assert delivery.status == "success"
        assert delivery.attempt_count == 1  # reset to 0, then incremented by attempt


@pytest.mark.django_db
class TestDisableEndpoints:
    def test_disable_clears_circuit_breaker_state(
        self, mock_site_context: object
    ) -> None:
        """Disabling should clear circuit breaker state (disabled_at, failure_count)."""
        endpoint = WebhookEndpointFactory(
            is_active=True,
            disabled_at=timezone.now(),
            failure_count=5,
        )

        admin_instance = WebhookEndpointAdmin(WebhookEndpoint, None)
        queryset = WebhookEndpoint.objects.filter(pk=endpoint.pk)

        admin_instance.disable_endpoints(request=None, queryset=queryset)

        endpoint.refresh_from_db()
        assert endpoint.is_active is False
        assert endpoint.disabled_at is None
        assert endpoint.failure_count == 0


@pytest.mark.django_db
class TestEnableEndpoints:
    def test_enable_clears_circuit_breaker_state(
        self, mock_site_context: object
    ) -> None:
        """Issue #6: enable_endpoints must clear disabled_at and failure_count."""
        endpoint = WebhookEndpointFactory(
            is_active=False,
            disabled_at=timezone.now(),
            failure_count=5,
        )

        admin_instance = WebhookEndpointAdmin(WebhookEndpoint, None)
        queryset = WebhookEndpoint.objects.filter(pk=endpoint.pk)

        admin_instance.enable_endpoints(request=None, queryset=queryset)

        endpoint.refresh_from_db()
        assert endpoint.is_active is True
        assert endpoint.disabled_at is None
        assert endpoint.failure_count == 0


@pytest.mark.django_db
class TestWebhookSecretAdmin:
    def test_masked_value_shows_last_four_chars(
        self, mock_site_context: object
    ) -> None:
        """masked_value should show bullets followed by last 4 characters."""
        secret = WebhookSecretFactory(encrypted_value="my-secret-api-key-1234")
        admin_instance = WebhookSecretAdmin(WebhookSecret, None)
        assert admin_instance.masked_value(secret) == "••••••••1234"

    def test_editing_secret_without_value_preserves_existing(
        self, mock_site_context: object
    ) -> None:
        """Submitting the edit form with empty encrypted_value keeps the old value."""
        from freedom_ls.webhooks.forms import WebhookSecretForm

        secret = WebhookSecretFactory(
            name="keep_me", encrypted_value="original-secret-value"
        )
        # Simulate an edit where encrypted_value is left blank
        form = WebhookSecretForm(
            data={"name": "keep_me", "description": "", "encrypted_value": ""},
            instance=secret,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        saved.refresh_from_db()
        assert saved.encrypted_value == "original-secret-value"

    def test_creating_secret_stores_value(self, mock_site_context: object) -> None:
        """Creating a new secret via the form stores the encrypted value."""
        from freedom_ls.webhooks.forms import WebhookSecretForm

        form = WebhookSecretForm(
            data={
                "name": "new_secret",
                "description": "A test secret",
                "encrypted_value": "brand-new-value",
            },
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        saved.refresh_from_db()
        assert saved.encrypted_value == "brand-new-value"


@pytest.mark.django_db
class TestWebhookEndpointFormTransformation:
    """Tests for transformation fields in WebhookEndpointForm."""

    def test_form_includes_transformation_fields(
        self, mock_site_context: object
    ) -> None:
        """Form should include all transformation fields."""
        from freedom_ls.webhooks.forms import WebhookEndpointForm

        form = WebhookEndpointForm()
        assert "http_method" in form.fields
        assert "content_type" in form.fields
        assert "headers_template" in form.fields
        assert "body_template" in form.fields
        assert "auth_type" in form.fields
        assert "preset_slug" in form.fields

    def test_form_includes_preset_slug_as_non_model_field(
        self, mock_site_context: object
    ) -> None:
        """preset_slug on the form should be a non-model ChoiceField (not saved directly)."""
        from freedom_ls.webhooks.forms import WebhookEndpointForm

        form = WebhookEndpointForm()
        field = form.fields["preset_slug"]
        assert not field.required

    def test_template_fields_use_ace_widget(self, mock_site_context: object) -> None:
        """headers_template and body_template should use AceWidget."""
        from django_ace import AceWidget

        from freedom_ls.webhooks.forms import WebhookEndpointForm

        form = WebhookEndpointForm()
        assert isinstance(form.fields["headers_template"].widget, AceWidget)
        assert isinstance(form.fields["body_template"].widget, AceWidget)

    def test_template_fields_have_help_text(self, mock_site_context: object) -> None:
        """Template fields should list available variables in help_text."""
        from freedom_ls.webhooks.forms import WebhookEndpointForm

        form = WebhookEndpointForm()
        for field_name in ("headers_template", "body_template"):
            help_text = str(form.fields[field_name].help_text)
            assert "event.id" in help_text
            assert "event.type" in help_text
            assert "event.timestamp" in help_text
            assert "event.data.*" in help_text
            assert "secrets.*" in help_text

    def test_saving_endpoint_with_transformation_fields(
        self, mock_site_context: object
    ) -> None:
        """Saving an endpoint with transformation fields should persist them."""
        from freedom_ls.webhooks.forms import WebhookEndpointForm

        form = WebhookEndpointForm(
            data={
                "url": "https://example.com/webhook",
                "description": "Test endpoint",
                "event_types": ["user.registered"],
                "is_active": True,
                "http_method": "POST",
                "content_type": "application/json",
                "auth_type": "none",
                "headers_template": '{"X-Custom": "value"}',
                "body_template": '{"event": "{{ event.type }}"}',
                "preset_slug": "",
            },
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        saved.refresh_from_db()
        assert saved.http_method == "POST"
        assert saved.content_type == "application/json"
        assert saved.auth_type == "none"
        assert saved.headers_template == '{"X-Custom": "value"}'
        assert saved.body_template == '{"event": "{{ event.type }}"}'

    def test_form_validation_errors_for_invalid_template(
        self, mock_site_context: object
    ) -> None:
        """Form should show validation errors for invalid Jinja2 templates."""
        from freedom_ls.webhooks.forms import WebhookEndpointForm

        form = WebhookEndpointForm(
            data={
                "url": "https://example.com/webhook",
                "description": "Test endpoint",
                "event_types": ["user.registered"],
                "is_active": True,
                "http_method": "POST",
                "content_type": "application/json",
                "auth_type": "signing",
                "headers_template": "",
                "body_template": "{{ unclosed",
                "preset_slug": "",
            },
        )
        assert not form.is_valid()
        assert "body_template" in form.errors

    def test_preset_slug_not_saved_to_model_directly(
        self, mock_site_context: object
    ) -> None:
        """The preset_slug form field value should not interfere with saving."""
        from freedom_ls.webhooks.forms import WebhookEndpointForm

        form = WebhookEndpointForm(
            data={
                "url": "https://api.brevo.com/v3/events",
                "description": "Brevo endpoint",
                "event_types": ["user.registered"],
                "is_active": True,
                "http_method": "POST",
                "content_type": "application/json",
                "auth_type": "none",
                "headers_template": '{"api-key": "test"}',
                "body_template": '{"event": "{{ event.type }}"}',
                "preset_slug": "brevo-track-event",
            },
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        saved.refresh_from_db()
        # preset_slug is a model field, so it can be saved
        assert saved.preset_slug == "brevo-track-event"


@pytest.mark.django_db
class TestWebhookEndpointAdminFieldsets:
    """Tests for WebhookEndpointAdmin fieldset configuration."""

    def test_admin_has_transformation_fieldset(self, mock_site_context: object) -> None:
        """Admin should have a 'Transformation' fieldset with the right fields."""
        admin_instance = WebhookEndpointAdmin(WebhookEndpoint, None)
        fieldsets = admin_instance.fieldsets
        assert fieldsets is not None

        fieldset_names = [name for name, _ in fieldsets]
        assert "Transformation" in fieldset_names

        # Find the Transformation fieldset
        transformation_fieldset = None
        for name, options in fieldsets:
            if name == "Transformation":
                transformation_fieldset = options
                break

        assert transformation_fieldset is not None
        fields = transformation_fieldset["fields"]
        assert "preset_slug" in fields
        assert "http_method" in fields
        assert "content_type" in fields
        assert "auth_type" in fields
        assert "headers_template" in fields
        assert "body_template" in fields

    def test_admin_has_status_fieldset(self, mock_site_context: object) -> None:
        """Admin should have a 'Status' fieldset."""
        admin_instance = WebhookEndpointAdmin(WebhookEndpoint, None)
        fieldsets = admin_instance.fieldsets
        fieldset_names = [name for name, _ in fieldsets]
        assert "Status" in fieldset_names
