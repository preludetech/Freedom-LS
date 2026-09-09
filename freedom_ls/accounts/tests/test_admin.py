"""Admin tests — `LegalConsent` is fully read-only, yet a user erasure carries it."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import LegalConsentFactory, UserFactory
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.referral_tracking.factories import SignupAttributionFactory
from freedom_ls.referral_tracking.models import SignupAttribution


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
