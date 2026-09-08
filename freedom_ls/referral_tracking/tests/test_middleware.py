"""Tests for `AttributionCaptureMiddleware`."""

from __future__ import annotations

import pytest

from django.http import HttpResponse
from django.test import Client, RequestFactory

from freedom_ls.referral_tracking.capture import (
    first_touch_from_request,
    set_attribution_cookie,
)
from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.middleware import AttributionCaptureMiddleware
from freedom_ls.referral_tracking.models import FirstTouchCount

ROBOTS_TXT = "/robots.txt"
COOKIE_NAME = config.REFERRAL_TRACKING_COOKIE_NAME

rf = RequestFactory()


@pytest.mark.django_db
def test_tracked_get_sets_a_httponly_cookie(mock_site_context) -> None:
    response = Client().get(ROBOTS_TXT, {"utm_source": "x"})

    assert response.cookies[COOKIE_NAME]["httponly"] is True


@pytest.mark.django_db
def test_tracked_get_sets_a_samesite_lax_cookie(mock_site_context) -> None:
    response = Client().get(ROBOTS_TXT, {"utm_source": "x"})

    assert response.cookies[COOKIE_NAME]["samesite"] == "Lax"


@pytest.mark.django_db
def test_tracked_get_sets_a_cookie_with_a_ninety_day_max_age(mock_site_context) -> None:
    response = Client().get(ROBOTS_TXT, {"utm_source": "x"})

    max_age = int(response.cookies[COOKIE_NAME]["max-age"])
    assert max_age == config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS * 86400


@pytest.mark.django_db
def test_tracked_get_sets_a_host_only_cookie(mock_site_context) -> None:
    response = Client().get(ROBOTS_TXT, {"utm_source": "x"})

    assert response.cookies[COOKIE_NAME]["domain"] == ""


@pytest.mark.django_db
def test_untracked_get_sets_no_cookie(mock_site_context) -> None:
    response = Client().get(ROBOTS_TXT)

    assert COOKIE_NAME not in response.cookies


@pytest.mark.django_db
def test_second_tracked_get_in_the_same_client_leaves_the_cookie_byte_identical(
    mock_site_context,
) -> None:
    client = Client()
    first_response = client.get(ROBOTS_TXT, {"utm_source": "x"})
    minted_value = first_response.cookies[COOKIE_NAME].value

    client.get(ROBOTS_TXT, {"utm_source": "x"})

    assert client.cookies[COOKIE_NAME].value == minted_value


@pytest.mark.django_db
def test_second_tracked_get_in_the_same_client_leaves_the_tally_at_one(
    mock_site_context, site
) -> None:
    client = Client()
    client.get(ROBOTS_TXT, {"utm_source": "x"})

    client.get(ROBOTS_TXT, {"utm_source": "x"})

    assert FirstTouchCount.objects.filter(site=site, utm_source="x").get().count == 1


@pytest.mark.django_db
def test_a_forged_cookie_is_replaced_as_if_absent(mock_site_context) -> None:
    client = Client()
    client.cookies[COOKIE_NAME] = "forged:value"

    response = client.get(ROBOTS_TXT, {"utm_source": "x"})

    assert response.cookies[COOKIE_NAME].value != "forged:value"


@pytest.mark.django_db
def test_the_minting_response_carries_vary_cookie(mock_site_context) -> None:
    response = Client().get(ROBOTS_TXT, {"utm_source": "x"})

    assert response.headers["Vary"] == "Cookie"


@pytest.mark.django_db
def test_the_minting_response_carries_private_no_store_cache_control(
    mock_site_context,
) -> None:
    response = Client().get(ROBOTS_TXT, {"utm_source": "x"})

    cache_control = response.headers["Cache-Control"]
    assert "private" in cache_control
    assert "no-store" in cache_control


@pytest.mark.django_db
def test_a_post_carrying_tracked_params_in_its_query_string_mints_no_cookie(
    mock_site_context,
) -> None:
    response = Client().post(f"{ROBOTS_TXT}?utm_source=x")

    assert COOKIE_NAME not in response.cookies


@pytest.mark.django_db
def test_a_post_carrying_tracked_params_in_its_query_string_mints_no_tally(
    mock_site_context, site
) -> None:
    Client().post(f"{ROBOTS_TXT}?utm_source=x")

    assert not FirstTouchCount.objects.filter(site=site, utm_source="x").exists()


def test_an_untracked_get_costs_no_query(db, django_assert_num_queries) -> None:
    request = rf.get("/")

    with django_assert_num_queries(0):
        AttributionCaptureMiddleware(lambda request: HttpResponse())(request)


def test_a_tracked_get_with_an_existing_valid_cookie_costs_no_query(
    db, django_assert_num_queries
) -> None:
    mint_request = rf.get("/?utm_source=x")
    first_touch = first_touch_from_request(mint_request)
    mint_response = HttpResponse()
    set_attribution_cookie(mint_response, first_touch)

    request = rf.get("/?utm_source=x")
    request.COOKIES[COOKIE_NAME] = mint_response.cookies[COOKIE_NAME].value

    with django_assert_num_queries(0):
        AttributionCaptureMiddleware(lambda request: HttpResponse())(request)
