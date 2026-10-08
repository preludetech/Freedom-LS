"""Tests for `SiteAwareSignupForm` and the shared form mixins in accounts.forms."""

from __future__ import annotations

import logging
import re

import pytest
from allauth.core.context import request_context

from django import forms
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.forms import HoneypotFormMixin, SiteAwareSignupForm
from freedom_ls.accounts.models import LegalConsent

User = get_user_model()


class _LabelledForm(HoneypotFormMixin, forms.Form):
    honeypot_context_label = "Labelled"


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
def test_first_name_optional_from_settings_default_when_no_policy(
    allauth_request_ctx, mock_site_context, settings
):
    """settings.REQUIRE_NAME=False with no policy → first_name optional."""
    settings.REQUIRE_NAME = False

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is False


@pytest.mark.django_db
def test_first_name_required_from_settings_default_when_no_policy(
    allauth_request_ctx, mock_site_context, settings
):
    """settings.REQUIRE_NAME=True with no policy → first_name required."""
    settings.REQUIRE_NAME = True

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is True


@pytest.mark.django_db
def test_policy_require_name_overrides_settings_default(
    allauth_request_ctx, mock_site_context, site, settings
):
    """A per-site policy with require_name=True overrides REQUIRE_NAME=False."""
    settings.REQUIRE_NAME = False
    SiteSignupPolicyFactory(site=site, require_name=True)

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is True


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


# Substrings of field names that browsers and password managers autofill. A
# honeypot whose name contains one of these gets filled for real people.
AUTOFILL_NAME_FRAGMENTS = [
    "name",
    "email",
    "mail",
    "website",
    "url",
    "homepage",
    "company",
    "organization",
    "organisation",
    "phone",
    "tel",
    "mobile",
    "address",
    "street",
    "city",
    "zip",
    "postal",
    "country",
    "user",
    "login",
    "password",
]

HONEYPOT_FIELD = "fax_number"
BOT_VALUE = "i-am-a-bot"


def _signup_data(**overrides: str) -> dict[str, str]:
    data = {
        "email": "honeypot@example.com",
        "password1": "Sup3rSecretPass!",  # pragma: allowlist secret
        "password2": "Sup3rSecretPass!",  # pragma: allowlist secret
        "first_name": "Test",
        "last_name": "Person",
        "accept_terms": "on",
        "accept_privacy": "on",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_honeypot_is_the_only_hidden_field(allauth_request_ctx, mock_site_context):
    form = SiteAwareSignupForm()

    assert [field.name for field in form.hidden_fields()] == [HONEYPOT_FIELD]


@pytest.mark.django_db
def test_honeypot_name_is_not_one_browsers_autofill(
    allauth_request_ctx, mock_site_context
):
    """Regression: `_hp` sat next to `last_name` and got filled with the surname."""
    form = SiteAwareSignupForm()

    for field in form.hidden_fields():
        assert not field.name.startswith("_")
        for fragment in AUTOFILL_NAME_FRAGMENTS:
            assert fragment not in field.name.lower()


@pytest.mark.django_db
def test_honeypot_rejects_submission_with_form_level_error(
    allauth_request_ctx, mock_site_context
):
    form = SiteAwareSignupForm(data=_signup_data(**{HONEYPOT_FIELD: BOT_VALUE}))

    assert form.is_valid() is False
    assert form.non_field_errors()
    assert set(form.errors) == {"__all__"}


@pytest.mark.django_db
def test_honeypot_trip_logs_one_warning_without_pii(
    allauth_request_ctx, mock_site_context, settings, caplog
):
    settings.TRUSTED_PROXY_IP_HEADER = None
    allauth_request_ctx.META["REMOTE_ADDR"] = "203.0.113.7"
    form = SiteAwareSignupForm(data=_signup_data(**{HONEYPOT_FIELD: BOT_VALUE}))

    with caplog.at_level(logging.WARNING, logger="freedom_ls.accounts.forms"):
        form.is_valid()

    records = [r for r in caplog.records if r.name == "freedom_ls.accounts.forms"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert records[0].levelno == logging.WARNING
    assert mock_site_context.domain in message
    assert "203.0.113.7" in message
    assert "honeypot@example.com" not in message
    assert BOT_VALUE not in message


@pytest.mark.django_db
def test_empty_honeypot_logs_nothing(
    allauth_request_ctx, mock_site_context, legal_repo_mock, caplog
):
    form = SiteAwareSignupForm(data=_signup_data())

    with caplog.at_level(logging.WARNING, logger="freedom_ls.accounts.forms"):
        form.is_valid()

    assert not [r for r in caplog.records if r.name == "freedom_ls.accounts.forms"]


@pytest.mark.django_db
def test_signup_page_renders_honeypot_inside_hidden_wrapper(mock_site_context):
    """Regression: an off-screen input can still take focus, so autofill filled it."""
    body = Client().get(reverse("account_signup")).content.decode()

    match = re.search(
        rf"<div hidden>\s*(<input[^>]*name=\"{HONEYPOT_FIELD}\"[^>]*>)\s*</div>", body
    )
    assert match, "honeypot input is not inside a <div hidden> wrapper"
    assert 'type="text"' in match.group(1)
    assert "-9999px" not in match.group(1)
    assert body.count(f'name="{HONEYPOT_FIELD}"') == 1


@pytest.mark.django_db
def test_filled_honeypot_rerenders_signup_page_with_message_and_no_user(
    mock_site_context,
):
    response = Client().post(
        reverse("account_signup"), _signup_data(**{HONEYPOT_FIELD: BOT_VALUE})
    )

    assert response.status_code == 200
    assert "try typing your details in by hand" in response.content.decode()
    assert not User.objects.filter(email="honeypot@example.com").exists()


@pytest.mark.django_db
def test_signup_with_empty_honeypot_creates_user(mock_site_context):
    Client().post(reverse("account_signup"), _signup_data(**{HONEYPOT_FIELD: ""}))

    assert User.objects.filter(email="honeypot@example.com").exists()


@pytest.mark.django_db
def test_honeypot_mixin_behaves_the_same_on_signup(
    allauth_request_ctx, mock_site_context, settings, caplog
) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = None
    allauth_request_ctx.META["REMOTE_ADDR"] = "203.0.113.7"
    form = SiteAwareSignupForm(data={"email": "bot@example.com", "fax_number": "x"})

    with caplog.at_level(logging.WARNING, logger="freedom_ls.accounts.forms"):
        form.is_valid()

    messages = [
        r.getMessage() for r in caplog.records if r.name == "freedom_ls.accounts.forms"
    ]
    assert messages == [
        f"Signup honeypot tripped on site {mock_site_context.domain} "
        "from IP 203.0.113.7"
    ]
    assert str(HoneypotFormMixin.honeypot_error_message) in form.non_field_errors()


@pytest.mark.django_db
def test_honeypot_mixin_logs_with_its_context_label(
    allauth_request_ctx, mock_site_context, settings, caplog
) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = None
    allauth_request_ctx.META["REMOTE_ADDR"] = "203.0.113.7"
    form = _LabelledForm(data={"fax_number": "x"})

    with caplog.at_level(logging.WARNING, logger="freedom_ls.accounts.forms"):
        form.is_valid()

    messages = [
        r.getMessage() for r in caplog.records if r.name == "freedom_ls.accounts.forms"
    ]
    assert messages == [
        f"Labelled honeypot tripped on site {mock_site_context.domain} "
        "from IP 203.0.113.7"
    ]
