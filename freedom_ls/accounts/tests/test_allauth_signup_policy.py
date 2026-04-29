from __future__ import annotations

import pytest

from django.test import RequestFactory, override_settings

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.factories import SiteFactory, SiteSignupPolicyFactory
from freedom_ls.accounts.models import SiteSignupPolicy
from freedom_ls.site_aware_models.models import _CACHED_SITE_ATTR


@pytest.mark.django_db
def test_falls_back_to_global_setting_when_no_policy(mock_site_context, settings):
    """If no SiteSignupPolicy exists for the current site, use settings.ALLOW_SIGN_UPS."""
    settings.ALLOW_SIGN_UPS = True

    request = RequestFactory().get("/")
    assert AccountAdapter().is_open_for_signup(request) is True


@pytest.mark.django_db
def test_policy_overrides_global_setting(mock_site_context, settings, site):
    """Per-site SiteSignupPolicy should override settings.ALLOW_SIGN_UPS."""
    settings.ALLOW_SIGN_UPS = False  # global signups are not allowed

    SiteSignupPolicy.objects.update_or_create(
        site=site,
        defaults={"allow_signups": True},  # per-site allows signups
    )

    request = RequestFactory().get("/")
    assert AccountAdapter().is_open_for_signup(request) is True


@pytest.mark.django_db
def test_policy_can_disable_when_global_allows(mock_site_context, settings, site):
    """Per-site SiteSignupPolicy can disable signups even if the global setting allows them."""
    settings.ALLOW_SIGN_UPS = True  # global signups are allowed

    SiteSignupPolicy.objects.update_or_create(
        site=site,
        defaults={"allow_signups": False},  # per-site signups are not allowed
    )

    request = RequestFactory().get("/")
    assert AccountAdapter().is_open_for_signup(request) is False


@pytest.mark.django_db
def test_is_open_for_signup_respects_force_site_name(settings):
    """is_open_for_signup should use the forced site's policy, not the request domain's."""
    forced_site = SiteFactory(name="ForcedSite", domain="forced.example.com")
    SiteFactory(name="DomainSite", domain="testserver")

    SiteSignupPolicyFactory(site=forced_site, allow_signups=False)
    settings.ALLOW_SIGN_UPS = True  # global default allows signups

    request = RequestFactory().get("/")  # domain = testserver

    with override_settings(FORCE_SITE_NAME="ForcedSite"):
        if hasattr(request, _CACHED_SITE_ATTR):
            delattr(request, _CACHED_SITE_ATTR)
        result = AccountAdapter().is_open_for_signup(request)

    assert result is False  # Should use ForcedSite's policy (disallow), not DomainSite
