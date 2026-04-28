"""Tests for accounts models — `LegalConsent` and extended `SiteSignupPolicy`."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import LegalConsent, SiteSignupPolicy
from freedom_ls.site_aware_models.models import _thread_locals


@pytest.mark.django_db
def test_site_signup_policy_defaults(mock_site_context, site):
    policy = SiteSignupPolicy.objects.create(site=site)

    assert policy.require_name is True
    assert policy.require_terms_acceptance is False
    assert policy.additional_registration_forms == []


@pytest.mark.django_db
def test_legal_consent_save_rejects_updates(mock_site_context):
    user = UserFactory()
    consent = LegalConsent.objects.create(
        user=user,
        document_type="terms",
        document_version="1.0",
        git_hash="abc123",
        ip_address="203.0.113.5",
    )

    consent.document_version = "2.0"

    with pytest.raises(ValueError, match="append-only"):
        consent.save()


@pytest.mark.django_db
def test_legal_consent_records_for_other_site_not_returned_in_current_site(
    mock_site_context, site, mocker
):
    """Cross-tenant isolation: LegalConsent rows from another site are filtered out."""
    user_in_current = UserFactory()
    LegalConsent.objects.create(
        user=user_in_current,
        document_type="terms",
        document_version="1.0",
        git_hash="hash-current",
    )

    # Create a second site & user with a consent record by switching the
    # active site temporarily (the SiteAwareModel auto-fills `site` from
    # the thread-local request).
    other_site = Site.objects.create(domain="other.example.com", name="OtherSite")

    original_request = _thread_locals.request
    other_mock_request = mocker.Mock()
    other_mock_request._cached_site = other_site
    _thread_locals.request = other_mock_request
    try:
        # Need to also create a user in the other site
        other_user = UserFactory()
        LegalConsent.objects.create(
            user=other_user,
            document_type="terms",
            document_version="1.0",
            git_hash="hash-other",
        )
    finally:
        _thread_locals.request = original_request

    visible = list(LegalConsent.objects.values_list("git_hash", flat=True))
    assert "hash-current" in visible
    assert "hash-other" not in visible


@pytest.mark.django_db
def test_legal_consent_site_set_automatically_on_create(mock_site_context, site):
    user = UserFactory()
    consent = LegalConsent.objects.create(
        user=user,
        document_type="privacy",
        document_version="1.0",
        git_hash="hash-priv",
    )

    assert consent.site == site
