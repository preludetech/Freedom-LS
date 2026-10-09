"""Tests for accounts models — `LegalConsent` and extended `SiteSignupPolicy`."""

from __future__ import annotations

import pytest

from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings

from freedom_ls.accounts.factories import (
    LegalConsentFactory,
    SiteFactory,
    SiteSignupPolicyFactory,
    UserFactory,
)
from freedom_ls.site_aware_models.models import _CACHED_SITE_ATTR, _thread_locals


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("first_name", "last_name", "email", "expected"),
    [
        # Both names present — first letter of each, uppercased.
        ("Mary", "Jane", "mj@example.com", "MJ"),
        ("ann", "adams", "aa@example.com", "AA"),
        # First name only, multi-token whitespace split — first letter of first two.
        ("Mary Jane", "", "x@example.com", "MJ"),
        # First name only, single token — first two letters.
        ("Mary", "", "x@example.com", "MA"),
        # Last name only, single token — first two letters.
        ("", "Jane", "x@example.com", "JA"),
        # Single character name — fine, returns it.
        ("x", "", "x@example.com", "X"),
        # Email-only fallback, alphabetic local-part start.
        ("", "", "jane@example.com", "JA"),
        # Email-only fallback, leading non-alphabetic chars skipped.
        ("", "", "123abc@x.com", "AB"),
        # Email-only fallback, leading emoji skipped.
        ("", "", "\U0001f31fabc@x.com", "AB"),
        # Diacritics preserved (no ASCII folding).
        ("Élise", "Önen", "e@example.com", "ÉÖ"),
        # Whitespace-only names fall through to email.
        ("   ", "   ", "jane@example.com", "JA"),
    ],
)
def test_user_initials(mock_site_context, first_name, last_name, email, expected):
    user = UserFactory.build(first_name=first_name, last_name=last_name, email=email)
    assert user.initials == expected


@pytest.mark.django_db
def test_user_initials_returns_none_when_email_local_part_has_no_letters(
    mock_site_context,
):
    user = UserFactory.build(first_name="", last_name="", email="123@x.com")
    assert user.initials is None


@pytest.mark.django_db
def test_user_initials_returns_none_when_everything_is_whitespace(mock_site_context):
    user = UserFactory.build(first_name="   ", last_name="   ", email="   @x.com")
    assert user.initials is None


@pytest.mark.django_db
def test_user_initials_non_latin_returns_single_grapheme(mock_site_context):
    """Non-Latin scripts return a single character rather than two."""
    user = UserFactory.build(first_name="王小明", last_name="", email="x@example.com")
    assert user.initials == "王"


@pytest.mark.django_db
def test_user_initials_normalises_decomposed_diacritics(mock_site_context):
    """A decomposed accent (E + combining acute) is folded to a single grapheme.

    Without NFC normalisation, slicing ``first[0]`` would yield bare ``E`` and
    drop the accent. NFC folds it back to precomposed ``É`` before slicing.
    """
    decomposed_first = "Élise"  # E + COMBINING ACUTE ACCENT
    decomposed_last = "Önen"  # O + COMBINING DIAERESIS
    user = UserFactory.build(
        first_name=decomposed_first, last_name=decomposed_last, email="e@example.com"
    )
    assert user.initials == "ÉÖ"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("first_name", "last_name", "email", "expected"),
    [
        ("Mary", "Jane", "mj@example.com", "Mary Jane"),
        ("Élise", "Önen", "e@example.com", "Élise Önen"),
        # First-name-only — keep returning the first name.
        ("Mary", "", "x@example.com", "Mary"),
        ("Mary Jane", "", "x@example.com", "Mary Jane"),
        # Last-name-only — return the last name rather than the email.
        ("", "Jane", "x@example.com", "Jane"),
        # No name → fall back to email.
        ("", "", "noname@example.com", "noname@example.com"),
        # Whitespace-only names fall through to email too.
        ("   ", "   ", "noname@example.com", "noname@example.com"),
    ],
)
def test_user_display_name(mock_site_context, first_name, last_name, email, expected):
    user = UserFactory.build(first_name=first_name, last_name=last_name, email=email)
    assert user.display_name == expected


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


User = get_user_model()


@pytest.mark.django_db
def test_user_manager_respects_force_site_name() -> None:
    """UserManager.get_queryset() should filter by the forced site, not request domain."""
    forced_site = SiteFactory(name="ForcedSite", domain="forced.example.com")
    domain_site = SiteFactory(name="DomainSite", domain="testserver")

    # Create users directly with explicit site assignment to bypass manager filtering
    forced_user = User(email="forced@example.com", site=forced_site)
    forced_user.set_password("testpass")
    forced_user.save()

    domain_user = User(email="domain@example.com", site=domain_site)
    domain_user.set_password("testpass")
    domain_user.save()

    request = RequestFactory().get("/")  # domain = testserver
    _thread_locals.request = request

    try:
        with override_settings(FORCE_SITE_NAME="ForcedSite"):
            # Clear any cached site on the request
            if hasattr(request, _CACHED_SITE_ATTR):
                delattr(request, _CACHED_SITE_ATTR)
            users = list(User.objects.all())

        assert len(users) == 1
        assert users[0].site == forced_site
        assert users[0].email == "forced@example.com"
    finally:
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
