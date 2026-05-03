"""Integration test that allauth's `ACCOUNT_RATE_LIMITS` actually fires for signup.

Marked `@pytest.mark.ci_only` because the windows are real-time and the
controlled wall-clock waits make the test too slow for a tight local loop.
The default local `uv run pytest` invocation excludes `ci_only`. CI must
include it (e.g. `uv run pytest -m "ci_only or not ci_only"`).

This guards against silent regressions from a typo'd allauth setting key
or the wrong value-format.
"""

from __future__ import annotations

import pytest

from django.test import Client, override_settings
from django.urls import reverse


def _post_signup(client: Client, email: str):
    return client.post(
        reverse("account_signup"),
        {
            "email": email,
            "password1": "Sup3rS3cretPass!",  # pragma: allowlist secret
            "password2": "Sup3rS3cretPass!",  # pragma: allowlist secret
            "first_name": "Rate",
            "last_name": "Test",
        },
    )


@pytest.mark.ci_only
@pytest.mark.django_db(transaction=True)
def test_signup_throttles_after_per_ip_limit(mock_site_context):
    """The third signup within the per-IP window is throttled by allauth."""
    client = Client()

    with override_settings(ACCOUNT_RATE_LIMITS={"signup": "2/m/ip"}):
        _post_signup(client, "r0@example.com")
        _post_signup(client, "r1@example.com")
        throttled = _post_signup(client, "r2@example.com")

    # allauth returns HTTP 429 for rate-limited signups.
    assert throttled.status_code == 429
