"""Admin tests — `LegalConsent` is fully read-only, yet a user erasure carries it."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import LegalConsentFactory, UserFactory
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.referral_tracking.factories import SignupAttributionFactory
from freedom_ls.referral_tracking.models import SignupAttribution
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context


@pytest.fixture
def staff_client(mock_site_context, db):
    user = UserFactory(superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_legal_consent_admin_add_returns_403(staff_client):
    response = staff_client.get(reverse("admin:freedom_ls_accounts_legalconsent_add"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_legal_consent_admin_change_does_not_persist_modification(
    staff_client, mock_site_context
):
    user = UserFactory()
    consent = LegalConsentFactory(user=user, git_hash="abc123")
    url = reverse("admin:freedom_ls_accounts_legalconsent_change", args=[consent.pk])

    response = staff_client.post(
        url,
        {
            "user": str(user.pk),
            "document_type": "privacy",
            "document_version": "9.9",
            "git_hash": "TAMPERED",
            "consent_method": "signup_checkbox",
        },
    )

    consent.refresh_from_db()
    assert consent.document_version == "1.0"
    assert consent.git_hash == "abc123"
    # 200 (re-render) or 403 (denied) is acceptable; 302 (saved + redirect)
    # is NOT.
    assert response.status_code != 302


@pytest.mark.django_db
def test_legal_consent_admin_delete_keeps_row(staff_client, mock_site_context):
    user = UserFactory()
    consent = LegalConsentFactory(user=user, git_hash="abc123")

    url = reverse("admin:freedom_ls_accounts_legalconsent_delete", args=[consent.pk])
    response = staff_client.post(url, {"post": "yes"})

    assert LegalConsent.objects.filter(pk=consent.pk).exists()
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_admin_delete_cascades_to_audit_rows(staff_client):
    user = UserFactory()
    LegalConsentFactory(user=user)
    SignupAttributionFactory(user=user)
    url = reverse("admin:freedom_ls_accounts_user_delete", args=[user.pk])

    response = staff_client.get(url)

    assert response.status_code == 200
    assert response.context["perms_lacking"] == set()

    response = staff_client.post(url, {"post": "yes"})

    assert response.status_code == 302
    assert not User.objects.filter(pk=user.pk).exists()
    assert not LegalConsent.objects.filter(user_id=user.pk).exists()
    assert not SignupAttribution.objects.filter(user_id=user.pk).exists()


@pytest.mark.django_db
def test_user_changelist_offers_the_export_action_and_button(staff_client):
    response = staff_client.get(reverse("admin:freedom_ls_accounts_user_changelist"))

    assert b"export_admin_action" in response.content
    assert reverse("admin:freedom_ls_accounts_user_export").encode() in response.content


@pytest.mark.django_db
def test_user_export_honours_the_changelist_filter(staff_client):
    plain = UserFactory(staff=False)

    response = staff_client.get(
        reverse("admin:freedom_ls_accounts_user_export") + "?is_staff__exact=1"
    )

    assert response["Content-Type"].startswith("text/csv")
    body = response.content.decode("utf-8-sig")
    assert plain.email not in body
    assert len(body.strip().splitlines()) == 2


@pytest.mark.django_db
def test_user_export_returns_403_without_any_accounts_permission(mock_site_context):
    user = UserFactory(staff=True)
    client = Client()
    client.force_login(user)

    response = client.get(reverse("admin:freedom_ls_accounts_user_export"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_user_export_omits_users_on_another_site(staff_client, site):
    other_site = SiteFactory()
    with site_context(other_site):
        other = UserFactory()

    response = staff_client.get(reverse("admin:freedom_ls_accounts_user_export"))

    assert other.email not in response.content.decode("utf-8-sig")
