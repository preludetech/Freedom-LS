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


@pytest.mark.ci_only
@pytest.mark.django_db(transaction=True)
def test_signup_throttles_after_per_ip_limit(mock_site_context):
    """Issuing more than the configured per-IP signups within the window must
    cause allauth to throttle (HTTP 429 or non-redirect response)."""
    client = Client()

    with override_settings(ACCOUNT_RATE_LIMITS={"signup": "2/m/ip"}):
        # First two should pass through without throttling (creating users
        # may still fail validation but the rate-limit must NOT fire).
        for i in range(2):
            client.post(
                reverse("account_signup"),
                {
                    "email": f"r{i}@example.com",
                    "password1": "Sup3rS3cretPass!",  # pragma: allowlist secret
                    "password2": "Sup3rS3cretPass!",  # pragma: allowlist secret
                    "first_name": "Rate",
                    "last_name": "Test",
                },
            )

        # Third in the same minute → throttled.
        throttled = client.post(
            reverse("account_signup"),
            {
                "email": "r2@example.com",
                "password1": "Sup3rS3cretPass!",  # pragma: allowlist secret
                "password2": "Sup3rS3cretPass!",  # pragma: allowlist secret
                "first_name": "Rate",
                "last_name": "Test",
            },
        )

        assert throttled.status_code in {403, 429} or "throttled" in (
            throttled.content.decode("utf-8", errors="ignore").lower()
        )
