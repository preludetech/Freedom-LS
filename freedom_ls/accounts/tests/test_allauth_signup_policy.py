import pytest
from django.test import RequestFactory

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.models import SiteSignupPolicy


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
