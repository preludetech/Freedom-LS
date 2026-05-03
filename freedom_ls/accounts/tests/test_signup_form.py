"""Tests for `SiteAwareSignupForm`."""

from __future__ import annotations

import logging

import pytest
from allauth.core.context import request_context

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.forms import SiteAwareSignupForm
from freedom_ls.accounts.models import LegalConsent


@pytest.fixture
def allauth_request_ctx(mock_site_context, rf):
    """Bind a request to allauth's context for the duration of a test."""
    request = rf.get("/")
    request._cached_site = mock_site_context
    with request_context(request):
        yield request


@pytest.mark.django_db
def test_first_name_required_by_default(allauth_request_ctx, mock_site_context):
    """Default policy (or no policy row) → first_name required."""
    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is True


@pytest.mark.django_db
def test_first_name_optional_when_policy_disables_require_name(
    allauth_request_ctx, mock_site_context, site
):
    SiteSignupPolicyFactory(site=site, require_name=False)

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is False


@pytest.mark.django_db
def test_form_adds_consent_checkboxes_when_required_and_docs_present(
    allauth_request_ctx, mock_site_context, site, legal_repo_mock
):
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    form = SiteAwareSignupForm()
    assert "accept_terms" in form.fields
    assert "accept_privacy" in form.fields
    assert form.fields["accept_terms"].required is True
    assert form.fields["accept_privacy"].required is True


@pytest.mark.django_db
def test_form_adds_consent_checkboxes_from_settings_default_when_no_policy(
    allauth_request_ctx, mock_site_context, legal_repo_mock, settings
):
    """When no SiteSignupPolicy exists for the site, settings.REQUIRE_TERMS_ACCEPTANCE
    drives whether consent checkboxes are added."""
    settings.REQUIRE_TERMS_ACCEPTANCE = True

    form = SiteAwareSignupForm()
    assert "accept_terms" in form.fields
    assert "accept_privacy" in form.fields


@pytest.mark.django_db
def test_form_omits_consent_checkboxes_when_settings_default_false(
    allauth_request_ctx, mock_site_context, legal_repo_mock, settings
):
    """settings.REQUIRE_TERMS_ACCEPTANCE=False with no policy → no checkboxes."""
    settings.REQUIRE_TERMS_ACCEPTANCE = False

    form = SiteAwareSignupForm()
    assert "accept_terms" not in form.fields
    assert "accept_privacy" not in form.fields


@pytest.mark.django_db
def test_policy_overrides_settings_default(
    allauth_request_ctx, mock_site_context, site, legal_repo_mock, settings
):
    """A per-site policy with require_terms_acceptance=False overrides
    a True global setting."""
    settings.REQUIRE_TERMS_ACCEPTANCE = True
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=False)

    form = SiteAwareSignupForm()
    assert "accept_terms" not in form.fields
    assert "accept_privacy" not in form.fields


@pytest.mark.django_db
def test_form_does_not_add_checkboxes_when_docs_missing(
    allauth_request_ctx, mock_site_context, site, mock_legal_blobs, caplog
):
    """When `require_terms_acceptance=True` but no docs resolve, the form
    omits the checkbox rather than rendering a broken link."""
    # No blobs registered → all lookups raise FileNotFoundError.
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    with caplog.at_level(logging.WARNING):
        form = SiteAwareSignupForm()

    assert "accept_terms" not in form.fields
    assert "accept_privacy" not in form.fields
    assert any("no terms doc" in r.message for r in caplog.records)


@pytest.mark.django_db
def test_custom_signup_records_consents(
    allauth_request_ctx, mock_site_context, site, legal_repo_mock, settings
):
    settings.TRUSTED_PROXY_IP_HEADER = None
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    form = SiteAwareSignupForm()
    form.cleaned_data = {
        "accept_terms": True,
        "accept_privacy": True,
    }

    user = UserFactory()
    request = allauth_request_ctx
    request.META["REMOTE_ADDR"] = "203.0.113.99"

    form.custom_signup(request, user)

    consents = list(LegalConsent.objects.filter(user=user).order_by("document_type"))
    assert len(consents) == 2
    consent_by_type = {c.document_type: c for c in consents}
    assert consent_by_type["privacy"].document_version == "1.5"
    assert consent_by_type["terms"].document_version == "1.5"
    assert consent_by_type["terms"].ip_address == "203.0.113.99"
    assert consent_by_type["terms"].consent_method == "signup_checkbox"
    assert consent_by_type["terms"].site == site


@pytest.mark.django_db
def test_custom_signup_records_nothing_when_no_consent_fields(
    allauth_request_ctx, mock_site_context, site, legal_repo_mock
):
    """If no consent fields are present (policy not requiring them), no rows."""
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=False)

    form = SiteAwareSignupForm()
    form.cleaned_data = {}

    user = UserFactory()

    form.custom_signup(allauth_request_ctx, user)

    assert LegalConsent.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_signup_view_renders_each_consent_checkbox_once(
    mock_site_context, site, legal_repo_mock
):
    """Regression for Bug 1 in better-registration QA report.

    When the policy requires consent and both legal docs resolve, the
    signup page must render exactly one checkbox per consent — not
    duplicates from both `{% element fields %}` and the linked-label
    block.
    """
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    response = Client().get(reverse("account_signup"))
    assert response.status_code == 200
    body = response.content.decode()

    assert body.count('name="accept_terms"') == 1
    assert body.count('name="accept_privacy"') == 1

    terms_url = reverse("accounts:legal_doc", kwargs={"doc_type": "terms"})
    privacy_url = reverse("accounts:legal_doc", kwargs={"doc_type": "privacy"})
    assert f'href="{terms_url}"' in body
    assert f'href="{privacy_url}"' in body


@pytest.mark.django_db
def test_honeypot_rejects_submission_when_filled(
    allauth_request_ctx, mock_site_context
):
    form = SiteAwareSignupForm(
        data={
            "email": "test@example.com",
            "password1": "Sup3rSecretPass!",  # pragma: allowlist secret
            "password2": "Sup3rSecretPass!",  # pragma: allowlist secret
            "first_name": "Test",
            "_hp": "i-am-a-bot",
        }
    )
    assert form.is_valid() is False
    assert "_hp" in form.errors
