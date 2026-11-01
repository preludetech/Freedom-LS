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


def test_the_key_text_is_absent_from_the_changelist_and_change_pages(
    issue, staff_client
):
    # Arrange
    key_text = issue().context["key_text"]
    key = ApiKey.objects.get()

    # Act
    changelist = staff_client.get(reverse("admin:freedom_ls_api_apikey_changelist"))
    change = staff_client.get(
        reverse("admin:freedom_ls_api_apikey_change", args=[key.pk])
    )

    # Assert
    assert key_text.encode() not in changelist.content
    assert key_text.encode() not in change.content


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


def test_an_invalid_add_issues_no_key_and_writes_no_entry(staff_client):
    # Act
    response = staff_client.post(reverse(ADD_URL), {"name": "Reporting"})

    # Assert
    assert response.status_code == 200
    assert ApiKey.objects.count() == 0
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
