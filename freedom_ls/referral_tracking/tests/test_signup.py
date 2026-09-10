"""Tests for the SignupAttribution row written on every signup.

Every test drives the real allauth signup form through `Client()`, the way a
learner actually reaches the `user_signed_up` receiver — there is no
direct-call path that bypasses the view.
"""

from __future__ import annotations

import pytest
import time_machine
from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from django.core import mail
from django.db import DatabaseError
from django.test import Client
from django.urls import reverse

from freedom_ls.referral_tracking.models import SignupAttribution

pytestmark = pytest.mark.django_db


def _signup_payload(email: str) -> dict[str, str]:
    """A signup form payload that passes validation."""
    return {
        "email": email,
        "password1": "TestPass123!xyz",  # pragma: allowlist secret
        "password2": "TestPass123!xyz",  # pragma: allowlist secret
        "first_name": "Signup",
        "last_name": "Attribution",
        "accept_terms": "on",
        "accept_privacy": "on",
    }


def _confirm_url_for(email: str) -> str:
    """The email-confirmation URL allauth would have emailed to `email`."""
    token = EmailConfirmationHMAC(EmailAddress.objects.get(email=email))
    return reverse("account_confirm_email", args=[token.key])


def test_signup_after_a_tracked_landing_records_the_landing(mock_site_context):
    client = Client()
    with time_machine.travel("2026-01-01T00:00:00+00:00", tick=False):
        client.get(
            "/robots.txt", {"utm_source": "newsletter", "utm_campaign": "spring"}
        )
    with time_machine.travel("2026-01-01T00:05:00+00:00", tick=False):
        client.post(reverse("account_signup"), _signup_payload("landed@example.com"))

    attribution = SignupAttribution.objects.get()

    assert attribution.utm_source == "newsletter"
    assert attribution.utm_campaign == "spring"
    assert attribution.signed_up_at > attribution.first_seen


def test_signup_with_no_landing_is_recorded_as_direct(mock_site_context):
    with time_machine.travel("2026-01-01T00:00:00+00:00", tick=False):
        Client().post(reverse("account_signup"), _signup_payload("direct@example.com"))

    attribution = SignupAttribution.objects.get()

    assert attribution.utm_source == "direct"
    assert attribution.utm_medium == "none"


@pytest.mark.parametrize(
    "field", ["advert_code", "utm_campaign", "utm_content", "utm_term", "gclid"]
)
def test_signup_with_no_landing_leaves_other_frozen_fields_blank(
    mock_site_context, field
):
    Client().post(reverse("account_signup"), _signup_payload(f"{field}@example.com"))

    attribution = SignupAttribution.objects.get(user__email=f"{field}@example.com")

    assert getattr(attribution, field) == ""


def test_signup_with_no_landing_has_first_seen_equal_to_signed_up_at(
    mock_site_context,
):
    with time_machine.travel("2026-01-01T00:00:00+00:00", tick=False):
        Client().post(reverse("account_signup"), _signup_payload("frozen@example.com"))

    attribution = SignupAttribution.objects.get()

    assert attribution.first_seen == attribution.signed_up_at


def test_ad_platform_cookies_on_the_client_are_recorded(mock_site_context):
    client = Client()
    client.cookies["_ga"] = "GA1.2.111.222"
    client.cookies["_fbp"] = "fb.1.111.222"
    client.cookies["_fbc"] = "fb.1.111.333"

    client.post(reverse("account_signup"), _signup_payload("adcookies@example.com"))

    attribution = SignupAttribution.objects.get()

    assert attribution.ga_cookie == "GA1.2.111.222"
    assert attribution.fbp_cookie == "fb.1.111.222"
    assert attribution.fbc_cookie == "fb.1.111.333"


def test_absent_ad_platform_cookies_are_recorded_as_blank(mock_site_context):
    Client().post(reverse("account_signup"), _signup_payload("noadcookies@example.com"))

    attribution = SignupAttribution.objects.get()

    assert attribution.ga_cookie == ""
    assert attribution.fbp_cookie == ""
    assert attribution.fbc_cookie == ""


def test_confirming_email_from_a_client_with_no_cookie_jar_leaves_the_row_unchanged(
    mock_site_context,
):
    signup_client = Client()
    signup_client.get("/robots.txt", {"utm_source": "newsletter"})
    signup_client.post(
        reverse("account_signup"), _signup_payload("confirm1@example.com")
    )
    before = SignupAttribution.objects.get()

    Client().post(_confirm_url_for("confirm1@example.com"), follow=True)

    after = SignupAttribution.objects.get()
    assert after.utm_source == before.utm_source
    assert after.signed_up_at == before.signed_up_at


def test_confirming_email_from_a_client_with_a_different_attribution_cookie_leaves_the_row_unchanged(
    mock_site_context,
):
    signup_client = Client()
    signup_client.get("/robots.txt", {"utm_source": "newsletter"})
    signup_client.post(
        reverse("account_signup"), _signup_payload("confirm2@example.com")
    )
    before = SignupAttribution.objects.get()

    confirming_client = Client()
    confirming_client.get("/robots.txt", {"utm_source": "other-campaign"})
    confirming_client.post(_confirm_url_for("confirm2@example.com"), follow=True)

    after = SignupAttribution.objects.get()
    assert after.utm_source == before.utm_source


def test_signup_and_confirmation_together_leave_exactly_one_row(mock_site_context):
    client = Client()
    client.get("/robots.txt", {"utm_source": "newsletter"})
    client.post(reverse("account_signup"), _signup_payload("onlyone@example.com"))

    client.post(_confirm_url_for("onlyone@example.com"), follow=True)

    assert SignupAttribution.objects.count() == 1


@pytest.fixture
def failing_attribution_write(mocker):
    """The SignupAttribution insert raises, as a dropped connection or bad inet would."""
    mocker.patch.object(
        SignupAttribution.objects, "create", side_effect=DatabaseError("boom")
    )
    return mocker.patch("freedom_ls.referral_tracking.signals.sentry_sdk")


def test_a_failed_attribution_write_does_not_fail_the_signup(
    mock_site_context, failing_attribution_write
):
    response = Client().post(
        reverse("account_signup"), _signup_payload("survives@example.com")
    )

    assert response.status_code == 302


def test_a_failed_attribution_write_still_sends_the_verification_mail(
    mock_site_context, failing_attribution_write
):
    Client().post(reverse("account_signup"), _signup_payload("mailed@example.com"))

    assert len(mail.outbox) == 1


def test_a_failed_attribution_write_leaves_no_row(
    mock_site_context, failing_attribution_write
):
    Client().post(reverse("account_signup"), _signup_payload("norow@example.com"))

    assert not SignupAttribution.objects.exists()


def test_a_failed_attribution_write_is_reported_to_sentry(
    mock_site_context, failing_attribution_write
):
    Client().post(reverse("account_signup"), _signup_payload("sentry@example.com"))

    failing_attribution_write.capture_exception.assert_called_once()
