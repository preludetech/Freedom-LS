"""The failure rate limits that sit above the account lockout.

The lockout keys on address and username together, so it never fires on an
address working through many usernames, nor on many addresses working through
one account. allauth's `login_failed` limit is what catches both, and these
tests pin the value and the behaviour.
"""

from __future__ import annotations

import pytest

from django.conf import settings as django_settings
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from config import settings_base

LOGIN_FAILED_LIMIT = "10/m/ip,5/5m/key"
TOO_MANY_ATTEMPTS = "Too many failed login attempts"


def _post_login(client: Client, email: str):
    return client.post(
        reverse("account_login"),
        {"login": email, "password": "wrong-password"},  # pragma: allowlist secret
    )


def test_login_failed_limit_is_stated_rather_than_inherited() -> None:
    """The value is written out, not left to allauth's computed default.

    Reads settings_base directly: the suite runs under settings_dev, which sets
    ACCOUNT_RATE_LIMITS to False and so carries no limits at all.
    """
    limits = settings_base.ACCOUNT_RATE_LIMITS
    assert isinstance(limits, dict)
    assert limits["login_failed"] == LOGIN_FAILED_LIMIT


def test_deprecated_login_attempts_settings_are_unset() -> None:
    """Defining either one re-derives login_failed and raises a check warning."""
    assert not hasattr(django_settings, "ACCOUNT_LOGIN_ATTEMPTS_LIMIT")
    assert not hasattr(django_settings, "ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT")


@pytest.mark.ci_only
@pytest.mark.django_db
def test_failed_logins_from_one_address_are_capped_before_any_lockout(
    mock_site_context,
) -> None:
    """One address working through many usernames is capped, and never locked.

    Eleven failures from one client, each naming a different address, leave every
    address and username pair on one failure, so the lockout cannot fire. The
    eleventh comes back as the login form carrying allauth's own error rather
    than the lockout page.
    """
    cache.clear()
    client = Client()

    with override_settings(ACCOUNT_RATE_LIMITS={"login_failed": LOGIN_FAILED_LIMIT}):
        for attempt in range(10):
            allowed = _post_login(client, f"spray{attempt}@example.com")
            assert TOO_MANY_ATTEMPTS not in allowed.content.decode()

        throttled = _post_login(client, "spray10@example.com")

    body = throttled.content.decode()
    assert TOO_MANY_ATTEMPTS in body
    assert "accounts/lockout.html" not in [
        template.name for template in throttled.templates
    ]
