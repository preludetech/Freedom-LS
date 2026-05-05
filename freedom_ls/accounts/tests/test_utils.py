"""Tests for `freedom_ls.accounts.utils`."""

from __future__ import annotations

import pytest

from django.test import RequestFactory

from freedom_ls.accounts.models import SiteSignupPolicy
from freedom_ls.accounts.utils import (
    get_client_ip,
    get_signup_policy_for_request,
)


def _request_with_meta(**meta: str):
    factory = RequestFactory()
    request = factory.get("/")
    for key, value in meta.items():
        request.META[key] = value
    return request


def test_get_client_ip_uses_remote_addr_when_no_proxy_header_configured(settings):
    settings.TRUSTED_PROXY_IP_HEADER = None
    request = _request_with_meta(REMOTE_ADDR="203.0.113.7")

    assert get_client_ip(request) == "203.0.113.7"


def test_get_client_ip_returns_leftmost_value_of_configured_header(settings):
    settings.TRUSTED_PROXY_IP_HEADER = "HTTP_X_FORWARDED_FOR"
    request = _request_with_meta(
        HTTP_X_FORWARDED_FOR="198.51.100.42, 10.0.0.1",
        REMOTE_ADDR="10.0.0.1",
    )

    assert get_client_ip(request) == "198.51.100.42"


def test_get_client_ip_falls_back_to_empty_string_when_nothing_set(settings):
    settings.TRUSTED_PROXY_IP_HEADER = None
    request = RequestFactory().get("/")
    # RequestFactory sets REMOTE_ADDR to "127.0.0.1" by default; remove it
    request.META.pop("REMOTE_ADDR", None)

    assert get_client_ip(request) == ""


def test_get_client_ip_falls_back_to_remote_addr_when_proxy_header_missing(settings):
    settings.TRUSTED_PROXY_IP_HEADER = "HTTP_X_FORWARDED_FOR"
    request = _request_with_meta(REMOTE_ADDR="10.0.0.5")

    assert get_client_ip(request) == "10.0.0.5"


@pytest.mark.django_db
def test_get_signup_policy_for_request_returns_none_when_no_policy(mock_site_context):
    request = RequestFactory().get("/")

    assert get_signup_policy_for_request(request) is None


@pytest.mark.django_db
def test_get_signup_policy_for_request_returns_policy_when_one_exists(
    mock_site_context, site
):
    policy = SiteSignupPolicy.objects.create(site=site, allow_signups=False)

    request = RequestFactory().get("/")

    assert get_signup_policy_for_request(request) == policy


def test_get_signup_policy_for_request_handles_none_request():
    assert get_signup_policy_for_request(None) is None
