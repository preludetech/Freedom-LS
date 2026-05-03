"""Tests for accounts models — `LegalConsent` and extended `SiteSignupPolicy`."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import (
    LegalConsentFactory,
    SiteFactory,
    SiteSignupPolicyFactory,
    UserFactory,
)
from freedom_ls.accounts.models import LegalConsent


@pytest.mark.django_db
def test_site_signup_policy_defaults(mock_site_context, site):
    policy = SiteSignupPolicyFactory(site=site)

    assert policy.require_name is True
    assert policy.require_terms_acceptance is False
    assert policy.additional_registration_forms == []


@pytest.mark.django_db
def test_legal_consent_save_rejects_updates(mock_site_context):
    consent = LegalConsentFactory(ip_address="203.0.113.5")

    consent.document_version = "2.0"

    with pytest.raises(ValueError, match="append-only"):
        consent.save()


@pytest.mark.django_db
def test_legal_consent_records_for_other_site_not_returned_in_current_site(
    mock_site_context,
):
    """Cross-tenant isolation: LegalConsent rows from another site are filtered out."""
    other_site = SiteFactory(name="OtherSite")

    LegalConsentFactory(git_hash="hash-current")
    other_user = UserFactory(site=other_site)
    LegalConsentFactory(user=other_user, site=other_site, git_hash="hash-other")

    visible = list(LegalConsent.objects.values_list("git_hash", flat=True))
    assert "hash-current" in visible
    assert "hash-other" not in visible


@pytest.mark.django_db
def test_legal_consent_site_set_automatically_on_create(mock_site_context, site):
    consent = LegalConsentFactory(document_type="privacy", git_hash="hash-priv")

    assert consent.site == site
