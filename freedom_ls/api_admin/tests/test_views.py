"""Tests for the revoke confirmation view."""

from __future__ import annotations

import pytest

from django.contrib import messages
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.models import ApiKey
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.tests.factories import SiteFactory

pytestmark = pytest.mark.django_db

REVOKE_URL = "admin:freedom_ls_api_apikey_revoke"


def _revoke_url(*keys: ApiKey) -> str:
    ids = ",".join(str(key.pk) for key in keys)
    return f"{reverse(REVOKE_URL)}?ids={ids}"


def _revoked_entries() -> int:
    return AuditLogEntry.unscoped.filter(action="api_key.revoked").count()


@pytest.fixture
def active_key(mock_site_context):
    return ApiKeyFactory(name="Reporting")


@pytest.fixture
def revoked_key(mock_site_context):
    return ApiKeyFactory(name="Old", revoked_at=timezone.now())


@pytest.fixture
def view_only_client(mock_site_context, logged_in_client):
    user = UserFactory(is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_apikey"))
    return logged_in_client(user)


def test_get_lists_active_keys_under_to_revoke(staff_client, active_key, revoked_key):
    # Act
    response = staff_client.get(_revoke_url(active_key, revoked_key))

    # Assert
    assert response.context["to_revoke"] == [active_key]


def test_get_lists_revoked_keys_under_already_revoked(
    staff_client, active_key, revoked_key
):
    # Act
    response = staff_client.get(_revoke_url(active_key, revoked_key))

    # Assert
    assert response.context["already_revoked"] == [revoked_key]


def test_get_revokes_nothing(staff_client, active_key):
    # Act
    staff_client.get(_revoke_url(active_key))

    # Assert
    active_key.refresh_from_db()
    assert active_key.revoked_at is None
    assert _revoked_entries() == 0


def test_post_revokes_each_active_key(staff_client, active_key, mock_site_context):
    # Arrange
    other = ApiKeyFactory()

    # Act
    staff_client.post(reverse(REVOKE_URL), {"ids": f"{active_key.pk},{other.pk}"})

    # Assert
    assert ApiKey.objects.filter(revoked_at__isnull=False).count() == 2


def test_post_writes_one_entry_per_revoked_key(
    staff_client, active_key, mock_site_context
):
    # Arrange
    other = ApiKeyFactory()

    # Act
    staff_client.post(reverse(REVOKE_URL), {"ids": f"{active_key.pk},{other.pk}"})

    # Assert
    assert _revoked_entries() == 2


def test_post_writes_no_entry_for_a_revoked_key(staff_client, active_key, revoked_key):
    # Act
    staff_client.post(reverse(REVOKE_URL), {"ids": f"{active_key.pk},{revoked_key.pk}"})

    # Assert
    assert _revoked_entries() == 1


def test_post_with_only_a_revoked_key_writes_nothing(staff_client, revoked_key):
    # Act
    staff_client.post(reverse(REVOKE_URL), {"ids": str(revoked_key.pk)})

    # Assert
    assert _revoked_entries() == 0


def test_get_with_only_revoked_keys_says_there_is_nothing_to_revoke(
    staff_client, revoked_key
):
    # Act
    response = staff_client.get(_revoke_url(revoked_key))

    # Assert
    content = response.content.decode()
    assert "Every selected key is already revoked. Nothing to revoke." in content
    assert 'id="already-revoked"' in content
    assert 'id="to-revoke"' not in content
    assert "stop at once" not in content


def test_get_with_only_revoked_keys_offers_no_revoke_button(staff_client, revoked_key):
    # Act
    response = staff_client.get(_revoke_url(revoked_key))

    # Assert
    content = response.content.decode()
    assert 'name="ids"' not in content
    assert f'href="{response.context["cancel_url"]}"' in content


def test_get_with_an_active_key_offers_the_revoke_button(
    staff_client, active_key, revoked_key
):
    # Act
    response = staff_client.get(_revoke_url(active_key, revoked_key))

    # Assert
    content = response.content.decode()
    assert 'name="ids"' in content
    assert 'id="to-revoke"' in content


def test_post_with_only_a_revoked_key_warns_that_nothing_was_revoked(
    staff_client, revoked_key
):
    # Act
    response = staff_client.post(
        reverse(REVOKE_URL), {"ids": str(revoked_key.pk)}, follow=True
    )

    # Assert
    flashed = [(m.level, m.message) for m in response.context["messages"]]
    assert flashed == [
        (messages.WARNING, "No API keys revoked: they were already revoked.")
    ]


def test_post_without_the_csrf_token_is_forbidden(staff_client, active_key):
    # Arrange
    client = Client(enforce_csrf_checks=True)
    client.cookies = staff_client.cookies

    # Act
    response = client.post(reverse(REVOKE_URL), {"ids": str(active_key.pk)})

    # Assert
    assert response.status_code == 403
    active_key.refresh_from_db()
    assert active_key.revoked_at is None


def test_get_by_a_user_with_view_permission_only_is_forbidden(
    view_only_client, active_key
):
    # Act
    response = view_only_client.get(_revoke_url(active_key))

    # Assert
    assert response.status_code == 403


def test_post_by_a_user_with_view_permission_only_is_forbidden(
    view_only_client, active_key
):
    # Act
    response = view_only_client.post(reverse(REVOKE_URL), {"ids": str(active_key.pk)})

    # Assert
    assert response.status_code == 403
    active_key.refresh_from_db()
    assert active_key.revoked_at is None


def test_another_sites_key_is_not_found(staff_client, mock_site_context):
    # Arrange
    foreign = ApiKeyFactory(site=SiteFactory(domain="other.example.com"))

    # Act
    response = staff_client.get(_revoke_url(foreign))

    # Assert
    assert response.status_code == 404


def test_a_malformed_id_is_not_found(staff_client):
    # Act
    response = staff_client.get(f"{reverse(REVOKE_URL)}?ids=not-a-uuid")

    # Assert
    assert response.status_code == 404


def test_revoking_one_key_redirects_to_its_change_page(staff_client, active_key):
    # Act
    response = staff_client.post(reverse(REVOKE_URL), {"ids": str(active_key.pk)})

    # Assert
    assert response.url == reverse(
        "admin:freedom_ls_api_apikey_change", args=[active_key.pk]
    )


def test_revoking_several_keys_redirects_to_the_changelist(
    staff_client, active_key, mock_site_context
):
    # Arrange
    other = ApiKeyFactory()

    # Act
    response = staff_client.post(
        reverse(REVOKE_URL), {"ids": f"{active_key.pk},{other.pk}"}
    )

    # Assert
    assert response.url == reverse("admin:freedom_ls_api_apikey_changelist")


def test_a_key_name_is_escaped_on_the_confirmation_page(
    staff_client, mock_site_context
):
    # Arrange
    key = ApiKeyFactory(name="<b>x</b>")

    # Act
    response = staff_client.get(_revoke_url(key))

    # Assert
    body = response.content.decode()
    assert "&lt;b&gt;x&lt;/b&gt;" in body
    assert "<b>x</b>" not in body
