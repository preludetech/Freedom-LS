"""Tests for `SiteAwareSignupForm`."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from allauth.core import context as allauth_context

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import LegalConsent, SiteSignupPolicy

from ._git_helpers import run_git as _git

_TERMS = """---
version: "1.5"
title: "Terms"
type: "terms"
effective_date: "2026-04-27"
---

Body.
"""

_PRIVACY = """---
version: "1.5"
title: "Privacy"
type: "privacy"
effective_date: "2026-04-27"
---

Body.
"""


@pytest.fixture
def legal_repo(tmp_path: Path, settings):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")

    default_dir = tmp_path / "legal_docs" / "_default"
    default_dir.mkdir(parents=True)
    (default_dir / "terms.md").write_text(_TERMS, encoding="utf-8")
    (default_dir / "privacy.md").write_text(_PRIVACY, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None
    return tmp_path


@pytest.fixture
def allauth_request_ctx(mock_site_context, rf):
    """Bind a request to allauth's context for the duration of a test."""
    request = rf.get("/")
    request._cached_site = mock_site_context
    token = allauth_context._request_var.set(request)
    try:
        yield request
    finally:
        allauth_context._request_var.reset(token)


@pytest.mark.django_db
def test_first_name_required_by_default(allauth_request_ctx, mock_site_context):
    """Default policy (or no policy row) → first_name required."""
    from freedom_ls.accounts.forms import SiteAwareSignupForm

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is True


@pytest.mark.django_db
def test_first_name_optional_when_policy_disables_require_name(
    allauth_request_ctx, mock_site_context, site
):
    SiteSignupPolicy.objects.create(site=site, require_name=False)

    from freedom_ls.accounts.forms import SiteAwareSignupForm

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is False


@pytest.mark.django_db
def test_form_adds_consent_checkboxes_when_required_and_docs_present(
    allauth_request_ctx, mock_site_context, site, legal_repo
):
    SiteSignupPolicy.objects.create(site=site, require_terms_acceptance=True)

    from freedom_ls.accounts.forms import SiteAwareSignupForm

    form = SiteAwareSignupForm()
    assert "accept_terms" in form.fields
    assert "accept_privacy" in form.fields
    assert form.fields["accept_terms"].required is True
    assert form.fields["accept_privacy"].required is True


@pytest.mark.django_db
def test_form_does_not_add_checkboxes_when_docs_missing(
    allauth_request_ctx, mock_site_context, site, tmp_path, settings, caplog
):
    """When `require_terms_acceptance=True` but no docs resolve, the form
    omits the checkbox rather than rendering a broken link."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "README.md").write_text("hi\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None

    SiteSignupPolicy.objects.create(site=site, require_terms_acceptance=True)

    from freedom_ls.accounts.forms import SiteAwareSignupForm

    with caplog.at_level(logging.WARNING):
        form = SiteAwareSignupForm()

    assert "accept_terms" not in form.fields
    assert "accept_privacy" not in form.fields
    assert any("no terms doc" in r.message for r in caplog.records)


@pytest.mark.django_db
def test_custom_signup_records_consents(
    allauth_request_ctx, mock_site_context, site, legal_repo, settings
):
    settings.TRUSTED_PROXY_IP_HEADER = None
    SiteSignupPolicy.objects.create(site=site, require_terms_acceptance=True)

    from freedom_ls.accounts.forms import SiteAwareSignupForm

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
    allauth_request_ctx, mock_site_context, site, legal_repo
):
    """If no consent fields are present (policy not requiring them), no rows."""
    SiteSignupPolicy.objects.create(site=site, require_terms_acceptance=False)

    from freedom_ls.accounts.forms import SiteAwareSignupForm

    form = SiteAwareSignupForm()
    form.cleaned_data = {}

    user = UserFactory()

    form.custom_signup(allauth_request_ctx, user)

    assert LegalConsent.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_signup_view_renders_each_consent_checkbox_once(
    mock_site_context, site, legal_repo
):
    """Regression for Bug 1 in better-registration QA report.

    When the policy requires consent and both legal docs resolve, the
    signup page must render exactly one checkbox per consent — not
    duplicates from both `{% element fields %}` and the linked-label
    block.
    """
    SiteSignupPolicy.objects.create(site=site, require_terms_acceptance=True)

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
    from freedom_ls.accounts.forms import SiteAwareSignupForm

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
