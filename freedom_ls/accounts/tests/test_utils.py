"""Tests for `freedom_ls.accounts.utils`."""

from __future__ import annotations

import pytest

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.utils.module_loading import import_string

from freedom_ls.accounts.factories import SiteFactory, SiteSignupPolicyFactory
from freedom_ls.accounts.models import SiteSignupPolicy
from freedom_ls.accounts.utils import (
    get_client_ip,
    get_signup_policy_for_request,
)
from freedom_ls.site_aware_models.models import _CACHED_SITE_ATTR, _thread_locals


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


def test_get_client_ip_returns_configured_header_value_verbatim(settings):
    settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"
    request = RequestFactory().get(
        "/",
        headers={"x-real-ip": "198.51.100.42"},
        REMOTE_ADDR="10.0.0.1",
    )

    assert get_client_ip(request) == "198.51.100.42"


def test_get_client_ip_returns_configured_header_ipv6_value(settings):
    settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"
    request = RequestFactory().get(
        "/",
        headers={"x-real-ip": "2001:db8::1"},
        REMOTE_ADDR="10.0.0.1",
    )

    assert get_client_ip(request) == "2001:db8::1"


def test_get_client_ip_raises_when_header_carries_several_addresses(settings):
    settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"
    request = RequestFactory().get(
        "/",
        headers={"x-real-ip": "198.51.100.42, 10.0.0.1"},
        REMOTE_ADDR="10.0.0.1",
    )

    # Never split: the leftmost entry of an appended header is whatever the visitor
    # typed. A comma means the edge appends rather than sets, so the value is
    # distrusted whole rather than picked apart.
    with pytest.raises(PermissionDenied):
        get_client_ip(request)


def test_get_client_ip_raises_when_header_is_not_an_address(settings):
    settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"
    request = RequestFactory().get(
        "/",
        headers={"x-real-ip": "not-an-address"},
        REMOTE_ADDR="10.0.0.1",
    )

    with pytest.raises(PermissionDenied):
        get_client_ip(request)


def test_get_client_ip_raises_when_header_value_not_disclosed_in_message(settings):
    settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"
    request = RequestFactory().get(
        "/",
        headers={"x-real-ip": "not-an-address"},
        REMOTE_ADDR="10.0.0.1",
    )

    with pytest.raises(PermissionDenied) as excinfo:
        get_client_ip(request)

    assert "not-an-address" not in str(excinfo.value)


def test_get_client_ip_falls_back_to_empty_string_when_nothing_set(settings):
    settings.TRUSTED_PROXY_IP_HEADER = None
    request = RequestFactory().get("/")
    # RequestFactory sets REMOTE_ADDR to "127.0.0.1" by default; remove it
    request.META.pop("REMOTE_ADDR", None)

    assert get_client_ip(request) == ""


def test_get_client_ip_raises_when_proxy_header_missing(settings):
    settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"
    request = _request_with_meta(REMOTE_ADDR="10.0.0.5")

    with pytest.raises(PermissionDenied):
        get_client_ip(request)


def test_axes_lockout_parameters_pairs_address_with_username_and_keeps_username(
    settings,
):
    # Two independent rules. The nested entry needs address and username together,
    # so one person's mistakes cannot lock out a shared NAT. The flat entry locks
    # on username alone, which is the only cap on a spray that rotates addresses
    # against one account at the Django admin login -- allauth's login_failed rate
    # limit does not wrap that view.
    assert settings.AXES_LOCKOUT_PARAMETERS == [
        ["ip_address", "username"],
        "username",
    ]


def test_axes_client_ip_callable_imports_to_get_client_ip(settings):
    assert import_string(settings.AXES_CLIENT_IP_CALLABLE) is get_client_ip


def test_axes_lockout_template_is_configured(settings):
    # Left unset, axes answers a lockout with its own bare plain-text body.
    assert settings.AXES_LOCKOUT_TEMPLATE == "accounts/lockout.html"


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


@pytest.mark.django_db
def test_get_signup_policy_for_request_uses_the_request_site_when_another_site_is_ambient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A leftover ambient site must not hide the policy the request asked for.

    A policy that reads as missing is not cosmetic here: the signup form falls
    back to the global defaults, stops asking for terms acceptance, and records
    no LegalConsent.
    """
    policy_site = SiteFactory(name="PolicySite", domain="policy.example.com")
    ambient_site = SiteFactory(name="AmbientSite", domain="ambient.example.com")
    policy = SiteSignupPolicyFactory(site=policy_site, allow_signups=False)

    ambient_request = RequestFactory().get("/")
    setattr(ambient_request, _CACHED_SITE_ATTR, ambient_site)
    monkeypatch.setattr(_thread_locals, "request", ambient_request, raising=False)

    request = RequestFactory().get("/")
    setattr(request, _CACHED_SITE_ATTR, policy_site)

    assert get_signup_policy_for_request(request) == policy
