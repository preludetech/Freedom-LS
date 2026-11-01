"""Tests for issuing an API key in the admin."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.contrib import admin as django_admin
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.models import ApiKey
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api_admin.admin import ApiKeyAdmin
from freedom_ls.api_admin.tests.helpers import offset_from
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.tests.audit_assertions import assert_entry

pytestmark = pytest.mark.django_db

ADD_URL = "admin:freedom_ls_api_apikey_add"


@pytest.fixture
def admin_user(staff_client):
    return get_user_model().objects.get(pk=staff_client.session["_auth_user_id"])


@pytest.fixture
def issue(staff_client):
    def _issue(name: str = "Reporting"):
        return staff_client.post(
            reverse(ADD_URL),
            {"name": name, "scopes": [ApiScope.USERS.value]},
        )

    return _issue


def test_issuing_a_key_shows_its_key_text_once_without_a_redirect(issue):
    # Act
    response = issue()

    # Assert
    key = ApiKey.objects.get()
    assert response.status_code == 200
    assert key.issued_key is None
    assert response.context["key_text"].startswith(f"flsk_{key.key_prefix}.")
    assert response.context["key_text"].encode() in response.content
    assert list(get_messages(response.wsgi_request)) == []
    assert "messages" not in response.cookies
    assert "no-store" in response["Cache-Control"]


def test_the_issued_key_belongs_to_the_host_site(issue, mock_site_context):
    # Act
    issue()

    # Assert
    assert ApiKey.objects.get().site == mock_site_context


def test_a_key_name_is_escaped_on_the_issued_page(issue):
    # Act
    response = issue("<script>x</script>")

    # Assert
    body = response.content.decode()
    assert "&lt;script&gt;x&lt;/script&gt;" in body
    assert "<script>x</script>" not in body


@pytest.mark.parametrize(
    ("url_name", "needs_pk"),
    [
        ("admin:freedom_ls_api_apikey_changelist", False),
        ("admin:freedom_ls_api_apikey_change", True),
    ],
)
def test_the_key_text_is_absent_from_the_page(issue, staff_client, url_name, needs_pk):
    # Arrange
    key_text = issue().context["key_text"]
    args = [ApiKey.objects.get().pk] if needs_pk else []

    # Act
    response = staff_client.get(reverse(url_name, args=args))

    # Assert
    assert key_text.encode() not in response.content


def test_the_admin_log_entry_points_at_the_saved_key(issue):
    # Act
    issue()

    # Assert
    log = LogEntry.objects.get()
    assert log.action_flag == ADDITION
    assert log.object_id == str(ApiKey.objects.get().pk)


def test_issuing_a_key_writes_an_audit_entry_without_the_key_text_or_hash(
    issue, admin_user
):
    # Act
    key_text = issue().context["key_text"]

    # Assert
    key = ApiKey.objects.get()
    entry = assert_entry(
        action="api_key.issued",
        actor=admin_user,
        target=key,
        target_label=str(key),
        organisation=None,
        details={
            "name": "Reporting",
            "key_prefix": key.key_prefix,
            "scopes": ["users"],
            "expires_at": None,
        },
    )
    assert key_text not in str(entry.details)
    assert key.key_hash not in str(entry.details)


def test_an_invalid_add_issues_no_key(staff_client):
    # Act
    response = staff_client.post(reverse(ADD_URL), {"name": "Reporting"})

    # Assert
    assert response.status_code == 200
    assert ApiKey.objects.count() == 0


def test_an_invalid_add_writes_no_audit_entry(staff_client):
    # Act
    staff_client.post(reverse(ADD_URL), {"name": "Reporting"})

    # Assert
    assert AuditLogEntry.unscoped.count() == 0


@pytest.mark.parametrize(
    ("revoked_delta", "expires_delta", "expected"),
    [
        (None, None, "Active"),
        (None, timedelta(days=-1), "Expired"),
        (timedelta(0), None, "Revoked"),
    ],
)
def test_the_status_column_names_each_state(
    mock_site_context, revoked_delta, expires_delta, expected
):
    # Arrange
    now = timezone.now()
    key = ApiKeyFactory(
        revoked_at=offset_from(now, revoked_delta),
        expires_at=offset_from(now, expires_delta),
    )
    model_admin = ApiKeyAdmin(ApiKey, django_admin.site)

    # Act / Assert
    assert model_admin.status(key) == expected


@pytest.fixture
def change_url():
    def _url(key: ApiKey) -> str:
        return reverse("admin:freedom_ls_api_apikey_change", args=[key.pk])

    return _url


def test_the_list_action_redirects_to_the_revoke_url_with_the_selected_ids(
    staff_client, mock_site_context
):
    # Arrange
    key = ApiKeyFactory()

    # Act
    response = staff_client.post(
        reverse("admin:freedom_ls_api_apikey_changelist"),
        {"action": "revoke_selected", "_selected_action": [str(key.pk)]},
    )

    # Assert
    assert response.url == (
        f"{reverse('admin:freedom_ls_api_apikey_revoke')}?ids={key.pk}"
    )


def test_the_detail_action_redirects_to_the_revoke_url_with_its_id(
    staff_client, mock_site_context
):
    # Arrange
    key = ApiKeyFactory()
    url = reverse("admin:freedom_ls_api_apikey_revoke_key", args=[key.pk])

    # Act
    response = staff_client.get(url)

    # Assert
    assert response.url == (
        f"{reverse('admin:freedom_ls_api_apikey_revoke')}?ids={key.pk}"
    )


def test_a_live_keys_change_form_accepts_a_new_name(
    staff_client, mock_site_context, change_url
):
    # Arrange
    key = ApiKeyFactory(name="Before")

    # Act
    staff_client.post(change_url(key), {"name": "After"})

    # Assert
    key.refresh_from_db()
    assert key.name == "After"


def test_a_live_keys_change_form_ignores_posted_scopes(
    staff_client, mock_site_context, change_url
):
    # Arrange
    key = ApiKeyFactory()

    # Act
    staff_client.post(change_url(key), {"name": "After", "scopes": ["bogus"]})

    # Assert
    key.refresh_from_db()
    assert key.scopes == [ApiScope.USERS]


def test_a_live_keys_change_form_ignores_a_posted_expiry(
    staff_client, mock_site_context, change_url
):
    # Arrange
    key = ApiKeyFactory()

    # Act
    staff_client.post(
        change_url(key),
        {"name": "After", "expires_at_0": "2030-01-01", "expires_at_1": "00:00:00"},
    )

    # Assert
    key.refresh_from_db()
    assert key.expires_at is None


@pytest.mark.parametrize(
    ("revoked_delta", "expires_delta"),
    [(timedelta(0), None), (None, timedelta(days=-1))],
)
def test_a_revoked_or_expired_key_has_no_editable_field(
    staff_client, mock_site_context, change_url, revoked_delta, expires_delta
):
    # Arrange
    now = timezone.now()
    key = ApiKeyFactory(
        revoked_at=offset_from(now, revoked_delta),
        expires_at=offset_from(now, expires_delta),
    )

    # Act
    response = staff_client.get(change_url(key))

    # Assert
    assert list(response.context["adminform"].form.fields) == []


def test_the_key_hash_appears_on_no_page(staff_client, mock_site_context, change_url):
    # Arrange
    key = ApiKeyFactory()

    # Act
    changelist = staff_client.get(reverse("admin:freedom_ls_api_apikey_changelist"))
    change = staff_client.get(change_url(key))

    # Assert
    assert key.key_hash.encode() not in changelist.content
    assert key.key_hash.encode() not in change.content


def test_delete_is_forbidden(staff_client, mock_site_context, change_url):
    # Arrange
    key = ApiKeyFactory()

    # Act
    response = staff_client.post(
        reverse("admin:freedom_ls_api_apikey_delete", args=[key.pk]), {"post": "yes"}
    )

    # Assert
    assert response.status_code == 403
    assert ApiKey.objects.filter(pk=key.pk).exists()


def test_the_change_page_offers_no_delete_link(
    staff_client, mock_site_context, change_url
):
    # Arrange
    key = ApiKeyFactory()

    # Act
    response = staff_client.get(change_url(key))

    # Assert
    assert response.context["has_delete_permission"] is False
