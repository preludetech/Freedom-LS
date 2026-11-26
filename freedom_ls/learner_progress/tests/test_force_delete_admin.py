"""The force delete confirmation page for users."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts import admin as accounts_admin
from freedom_ls.accounts.factories import LegalConsentFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import REASON_LENGTH, AuditLogEntry
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

FORCE_DELETE = "admin:freedom_ls_accounts_user_force_delete"


def _url(*users: User) -> str:
    ids = ",".join(str(user.pk) for user in users)
    return f"{reverse(FORCE_DELETE)}?ids={ids}"


@pytest.fixture
def staff_with_every_user_permission(mock_site_context, logged_in_client) -> Client:
    user = UserFactory(staff=True)
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="freedom_ls_accounts",
            content_type__model="user",
        )
    )
    client: Client = logged_in_client(user)
    return client


def test_change_page_offers_force_delete_to_a_superuser(staff_client) -> None:
    user = UserFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    )

    assert "Force delete" in response.content.decode()


def test_change_page_hides_force_delete_from_staff(
    staff_with_every_user_permission,
) -> None:
    user = UserFactory()

    response = staff_with_every_user_permission.get(
        reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    )

    assert response.status_code == 200
    assert "Force delete" not in response.content.decode()


def test_detail_action_redirects_to_the_confirmation_page(staff_client) -> None:
    user = UserFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_accounts_user_force_delete_one", args=[user.pk])
    )

    assert response.status_code == 302
    assert response.url == _url(user)


@pytest.mark.parametrize("method", ["get", "post"])
def test_staff_without_superuser_get_403(
    staff_with_every_user_permission, method: str
) -> None:
    user = UserFactory()

    response = getattr(staff_with_every_user_permission, method)(_url(user))

    assert response.status_code == 403


def test_page_links_deactivate_the_user_to_the_change_page(staff_client) -> None:
    user = UserFactory()

    response = staff_client.get(_url(user))

    change_url = reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    body = response.content.decode()
    assert "deactivate the user" in body
    assert f'href="{change_url}"' in body


def test_page_counts_each_model_once(staff_client) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)
    LegalConsentFactory(user=user, document_type="privacy")

    response = staff_client.get(_url(user))

    plan = response.context["plan"]
    assert plan.counts()["legal consents"] == 2
    assert plan.counts()["users"] == 1


@pytest.mark.parametrize(
    "reason", [None, "   ", "x" * (REASON_LENGTH + 1)], ids=["missing", "blank", "long"]
)
def test_invalid_reason_rerenders_with_422_and_deletes_nothing(
    staff_client, reason: str | None
) -> None:
    user = UserFactory()
    data = {"ids": str(user.pk)}
    if reason is not None:
        data["reason"] = reason

    response = staff_client.post(_url(user), data)

    assert response.status_code == 422
    assert "reason" in response.context["form"].errors
    assert User.objects.filter(pk=user.pk).exists()


def test_blocking_model_is_named_and_no_form_is_offered(
    staff_client, monkeypatch
) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    response = staff_client.get(_url(user))

    body = response.content.decode()
    assert "legal consent" in response.context["plan"].blocking_models
    assert "legal consent" in body
    assert "cannot run" in body
    assert 'name="reason"' not in body


def test_blocked_post_deletes_nothing(staff_client, monkeypatch) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    response = staff_client.post(_url(user), {"ids": str(user.pk), "reason": "Why"})

    assert response.status_code == 422
    assert User.objects.filter(pk=user.pk).exists()


def test_another_sites_user_is_a_404_on_get(staff_client) -> None:
    with site_context(SiteFactory()):
        other = UserFactory()

    response = staff_client.get(_url(other))

    assert response.status_code == 404


def test_another_sites_user_is_a_404_on_post_and_survives(staff_client) -> None:
    with site_context(SiteFactory()):
        other = UserFactory()

    response = staff_client.post(_url(other), {"ids": str(other.pk), "reason": "Why"})

    assert response.status_code == 404
    assert User._base_manager.filter(pk=other.pk).exists()


def test_malformed_id_is_a_404(staff_client) -> None:
    response = staff_client.get(f"{reverse(FORCE_DELETE)}?ids=not-a-number")

    assert response.status_code == 404


def test_post_deletes_the_user_and_records_the_reason(staff_client) -> None:
    user = UserFactory()
    user_pk = user.pk

    response = staff_client.post(
        _url(user), {"ids": str(user.pk), "reason": "Erasure requested"}
    )

    entry = AuditLogEntry.unscoped.get()
    assert response.status_code == 302
    assert response.url == reverse("admin:freedom_ls_accounts_user_changelist")
    assert not User._base_manager.filter(pk=user_pk).exists()
    assert entry.action == "user.deleted"
    assert entry.reason == "Erasure requested"
    assert entry.organisation is None


def test_page_lists_each_model_in_a_labelled_scrollable_region(staff_client) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)

    response = staff_client.get(_url(user))

    body = response.content.decode()
    assert 'aria-label="legal consents"' in body
    assert 'role="region"' in body
    assert 'data-icon="dropdown"' in body
