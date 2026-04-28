"""Admin tests — `LegalConsent` is fully read-only."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import LegalConsent


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
    consent = LegalConsent.objects.create(
        user=user,
        document_type="terms",
        document_version="1.0",
        git_hash="abc123",
    )
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
    consent = LegalConsent.objects.create(
        user=user,
        document_type="terms",
        document_version="1.0",
        git_hash="abc123",
    )

    url = reverse("admin:freedom_ls_accounts_legalconsent_delete", args=[consent.pk])
    response = staff_client.post(url, {"post": "yes"})

    assert LegalConsent.objects.filter(pk=consent.pk).exists()
    assert response.status_code != 302 or response.url.endswith("/")
