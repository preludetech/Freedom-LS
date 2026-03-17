from unittest.mock import patch

import httpx
import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.webhooks.factories import WebhookEndpointFactory, WebhookSecretFactory
from freedom_ls.webhooks.models import WebhookDelivery, WebhookEvent


@pytest.fixture
def admin_user(mock_site_context: object) -> object:
    """Create a superuser for admin access."""
    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture
def regular_user(mock_site_context: object) -> object:
    """Create a non-staff user."""
    return UserFactory(is_staff=False, is_superuser=False)


def _send_test_form_url(endpoint_pk: object) -> str:
    return reverse(
        "admin:webhooks_webhookendpoint_send_test_form",
        args=[endpoint_pk],
    )


def _send_test_result_url(endpoint_pk: object) -> str:
    return reverse(
        "admin:webhooks_webhookendpoint_send_test_result",
        args=[endpoint_pk],
    )


@pytest.mark.django_db
class TestSendTestFormView:
    def test_loads_and_shows_event_types(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """Send test form should load and display event type options."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered", "course.completed"],
        )
        client.force_login(admin_user)
        response = client.get(_send_test_form_url(endpoint.pk))
        assert response.status_code == 200
        content = response.content.decode()
        assert "user.registered" in content
        assert "course.completed" in content

    def test_shows_all_available_event_types(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """Form should show all available event types, not just subscribed ones."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
        )
        client.force_login(admin_user)
        response = client.get(_send_test_form_url(endpoint.pk))
        assert response.status_code == 200
        content = response.content.decode()
        assert "course.completed" in content
        assert "course.registered" in content

    def test_non_admin_cannot_access(
        self, regular_user: object, mock_site_context: object, client: object
    ) -> None:
        """Non-admin users should be redirected (permission denied)."""
        endpoint = WebhookEndpointFactory()
        client.force_login(regular_user)
        response = client.get(_send_test_form_url(endpoint.pk))
        assert response.status_code == 302  # Redirect to login

    def test_anonymous_user_cannot_access(
        self, mock_site_context: object, client: object
    ) -> None:
        """Anonymous users should be redirected."""
        endpoint = WebhookEndpointFactory()
        response = client.get(_send_test_form_url(endpoint.pk))
        assert response.status_code == 302


@pytest.mark.django_db
class TestSendTestResultView:
    def test_creates_event_and_delivery(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """Submitting the form should create a WebhookEvent and WebhookDelivery."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
        )
        client.force_login(admin_user)

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            response = client.post(
                _send_test_result_url(endpoint.pk),
                data={"event_type": "user.registered"},
            )

        assert response.status_code == 200
        assert WebhookEvent.objects.count() == 1
        assert WebhookDelivery.objects.count() == 1

    def test_event_has_test_flag_in_payload(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """The created event should have _test: True merged into the payload."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
        )
        client.force_login(admin_user)

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            client.post(
                _send_test_result_url(endpoint.pk),
                data={"event_type": "user.registered"},
            )

        event = WebhookEvent.objects.first()
        assert event is not None
        assert event.payload["_test"] is True

    def test_event_uses_sample_data(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """The event payload should contain sample data from WEBHOOK_EVENT_TYPE_SAMPLES."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
        )
        client.force_login(admin_user)

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            client.post(
                _send_test_result_url(endpoint.pk),
                data={"event_type": "user.registered"},
            )

        event = WebhookEvent.objects.first()
        assert event is not None
        assert event.payload["user_id"] == "sample-uuid-1234"
        assert event.payload["user_email"] == "test@example.com"

    def test_response_details_displayed(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """Result page should show response status code and body."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
        )
        client.force_login(admin_user)

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            response = client.post(
                _send_test_result_url(endpoint.pk),
                data={"event_type": "user.registered"},
            )

        content = response.content.decode()
        assert "200" in content

    def test_transformed_endpoint_shows_rendered_preview(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """Transformed endpoints should show a rendered request preview."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
            http_method="POST",
            content_type="application/json",
            body_template='{"user": "{{ event.data.user_email }}"}',
            auth_type="none",
        )
        client.force_login(admin_user)

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            response = client.post(
                _send_test_result_url(endpoint.pk),
                data={"event_type": "user.registered"},
            )

        content = response.content.decode()
        assert "Preview" in content
        assert endpoint.url in content

    def test_transformed_endpoint_masks_secrets_in_preview(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """Secrets in rendered headers should be masked in the preview."""
        WebhookSecretFactory(
            name="api_key",
            encrypted_value="super-secret-key-1234",
        )
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
            http_method="POST",
            content_type="application/json",
            headers_template='{"Authorization": "Bearer {{ secrets.api_key }}"}',
            body_template='{"user": "{{ event.data.user_email }}"}',
            auth_type="none",
        )
        client.force_login(admin_user)

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            response = client.post(
                _send_test_result_url(endpoint.pk),
                data={"event_type": "user.registered"},
            )

        content = response.content.decode()
        # The actual secret value should NOT appear
        assert "super-secret-key-1234" not in content
        # The masked version should appear
        assert "1234" in content

    def test_non_transformed_endpoint_skips_preview(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """Non-transformed endpoints should not show a rendered request preview."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
            body_template="",
        )
        client.force_login(admin_user)

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            response = client.post(
                _send_test_result_url(endpoint.pk),
                data={"event_type": "user.registered"},
            )

        content = response.content.decode()
        assert "Preview" not in content

    def test_non_admin_cannot_access(
        self, regular_user: object, mock_site_context: object, client: object
    ) -> None:
        """Non-admin users should be denied access to the result view."""
        endpoint = WebhookEndpointFactory()
        client.force_login(regular_user)
        response = client.post(
            _send_test_result_url(endpoint.pk),
            data={"event_type": "user.registered"},
        )
        assert response.status_code == 302

    def test_get_request_not_allowed(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """Result view should only accept POST requests."""
        endpoint = WebhookEndpointFactory()
        client.force_login(admin_user)
        response = client.get(_send_test_result_url(endpoint.pk))
        assert response.status_code == 405

    def test_event_uses_endpoint_site_id(
        self, admin_user: object, mock_site_context: object, client: object
    ) -> None:
        """The created event should use the endpoint's site_id."""
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
        )
        client.force_login(admin_user)

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            client.post(
                _send_test_result_url(endpoint.pk),
                data={"event_type": "user.registered"},
            )

        event = WebhookEvent.objects.first()
        assert event is not None
        assert event.site_id == endpoint.site_id
