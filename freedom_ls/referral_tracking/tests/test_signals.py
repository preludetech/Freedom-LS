"""Tests for the SignupAttribution row written on every signup.

Every test drives the real allauth signup form through `Client()`, the way a
learner actually reaches the `user_signed_up` receiver — there is no
direct-call path that bypasses the view.
"""

from __future__ import annotations

import datetime

import pytest
import time_machine
from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import DatabaseError
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.factories import AttributionTouchFactory
from freedom_ls.referral_tracking.models import (
    AttributionTouch,
    Conversion,
    ConversionKind,
    SignupAttribution,
    TouchSource,
)

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


def test_signup_after_a_referral_landing_records_the_code(mock_site_context):
    client = Client()
    client.get("/robots.txt", {"ref": "mrbeast", "utm_source": "newsletter"})
    client.post(reverse("account_signup"), _signup_payload("referred@example.com"))

    attribution = SignupAttribution.objects.get()

    assert attribution.referral_code == "mrbeast"


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
    return mocker.patch("freedom_ls.referral_tracking.best_effort.sentry_sdk")


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


DAY_ONE = datetime.datetime(2026, 3, 1, 12, 0, tzinfo=datetime.UTC)
DAY_THREE = DAY_ONE + datetime.timedelta(days=2)
DAY_FIVE = DAY_ONE + datetime.timedelta(days=4)
SIGNUP_TIME = DAY_ONE + datetime.timedelta(days=6)
COOKIE_NAME = config.REFERRAL_TRACKING_COOKIE_NAME


def _land(client: Client, when: datetime.datetime, **params: str) -> None:
    with time_machine.travel(when, tick=False):
        client.get("/robots.txt", params)


def _client_with_three_landings() -> Client:
    client = Client()
    _land(client, DAY_ONE, ref="A")
    _land(client, DAY_THREE, ref="B")
    _land(client, DAY_FIVE, utm_source="newsletter")
    return client


def _sign_up(client: Client, email: str, when: datetime.datetime = SIGNUP_TIME):
    with time_machine.travel(when, tick=False):
        return client.post(reverse("account_signup"), _signup_payload(email))


def test_a_signup_after_three_landings_writes_three_signup_flush_touches(
    mock_site_context,
) -> None:
    client = _client_with_three_landings()

    _sign_up(client, "three@example.com")

    touches = AttributionTouch._base_manager.order_by("occurred_at")
    assert [(t.occurred_at, t.recorded_via) for t in touches] == [
        (DAY_ONE, TouchSource.SIGNUP_FLUSH),
        (DAY_THREE, TouchSource.SIGNUP_FLUSH),
        (DAY_FIVE, TouchSource.SIGNUP_FLUSH),
    ]


def test_a_signup_writes_one_account_signup_conversion_freezing_the_coded_touches(
    mock_site_context,
) -> None:
    client = _client_with_three_landings()

    _sign_up(client, "convert@example.com")

    conversion = Conversion._base_manager.get(kind=ConversionKind.ACCOUNT_SIGNUP)
    assert (conversion.first_referral_code, conversion.last_referral_code) == (
        "A",
        "B",
    )


def test_the_signup_response_deletes_the_attribution_cookie(mock_site_context) -> None:
    client = _client_with_three_landings()

    response = _sign_up(client, "cleared@example.com")

    assert response.cookies[COOKIE_NAME]["max-age"] == 0


def test_a_signup_whose_touches_are_already_written_writes_no_duplicate(
    mock_site_context,
) -> None:
    client = _client_with_three_landings()
    user = UserFactory()
    for code, source, when in (
        ("A", "", DAY_ONE),
        ("B", "", DAY_THREE),
        ("", "newsletter", DAY_FIVE),
    ):
        AttributionTouchFactory(
            user=user, referral_code=code, utm_source=source, occurred_at=when
        )

    _sign_up(client, "seeded@example.com")

    # The seeded rows belong to a different user, so the new account gets its
    # own three and nothing is written twice for it.
    new_user = get_user_model().objects.get(email="seeded@example.com")
    assert AttributionTouch._base_manager.filter(user=new_user).count() == 3


def test_a_login_with_the_cookie_after_signup_flush_writes_no_duplicate(
    mock_site_context,
) -> None:
    client = _client_with_three_landings()
    _sign_up(client, "again@example.com")
    user = get_user_model().objects.get(email="again@example.com")
    EmailAddress.objects.filter(user=user).update(verified=True)
    client.cookies[COOKIE_NAME] = (
        _client_with_three_landings().cookies[COOKIE_NAME].value
    )

    with time_machine.travel(SIGNUP_TIME, tick=False):
        client.post(
            reverse("account_login"),
            {
                "login": "again@example.com",
                "password": "TestPass123!xyz",  # pragma: allowlist secret
            },
        )

    assert AttributionTouch._base_manager.filter(user=user).count() == 3


def test_a_login_with_a_cookie_writes_login_flush_touches(mock_site_context) -> None:
    user = UserFactory()
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    client = _client_with_three_landings()

    with time_machine.travel(SIGNUP_TIME, tick=False):
        client.post(
            reverse("account_login"), {"login": user.email, "password": user.email}
        )

    sources = AttributionTouch._base_manager.filter(user=user).values_list(
        "recorded_via", flat=True
    )
    assert set(sources) == {TouchSource.LOGIN_FLUSH}


def test_a_failed_conversion_write_does_not_fail_the_signup(
    mock_site_context, mocker
) -> None:
    mocker.patch.object(
        Conversion._base_manager, "get_or_create", side_effect=DatabaseError("boom")
    )
    mocker.patch("freedom_ls.referral_tracking.best_effort.sentry_sdk")

    response = Client().post(
        reverse("account_signup"), _signup_payload("conversionfail@example.com")
    )

    assert response.status_code == 302
    assert get_user_model().objects.filter(email="conversionfail@example.com").exists()


def test_two_landings_weeks_apart_then_signup_freeze_the_first_and_last_codes(
    mock_site_context,
) -> None:
    client = Client()
    _land(client, DAY_ONE, ref="A")
    three_weeks_on = DAY_ONE + datetime.timedelta(days=21)
    _land(client, three_weeks_on, ref="B")

    _sign_up(client, "journey@example.com", three_weeks_on)

    conversion = Conversion._base_manager.get(kind=ConversionKind.ACCOUNT_SIGNUP)
    assert AttributionTouch._base_manager.count() == 2
    assert (conversion.first_referral_code, conversion.last_referral_code) == (
        "A",
        "B",
    )
