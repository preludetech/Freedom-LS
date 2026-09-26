"""Tests for `acquisition_login_required`, the login_required variant that
sends an anonymous visitor to signup rather than straight to login."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.urls import reverse

from freedom_ls.accounts.decorators import acquisition_login_required
from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory


def _next_param(location: str) -> str | None:
    """Return the single `next` query-param value from a redirect Location, if any."""
    values = parse_qs(urlparse(location).query).get("next")
    return values[0] if values else None


def _view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("view reached")


@pytest.mark.django_db
def test_anonymous_request_is_sent_to_signup_with_next(mock_site_context, rf):
    request = rf.get("/somewhere/?a=1")
    request.user = AnonymousUser()

    response = acquisition_login_required(_view)(request)

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_signup"))
    assert _next_param(response["Location"]) == "/somewhere/?a=1"


@pytest.mark.django_db
def test_authenticated_request_reaches_the_view(mock_site_context, rf):
    request = rf.get("/somewhere/")
    request.user = UserFactory()

    response = acquisition_login_required(_view)(request)

    assert response.content == b"view reached"


@pytest.mark.django_db
def test_htmx_request_gets_hx_redirect(mock_site_context, rf):
    request = rf.get("/somewhere/?a=1", HTTP_HX_REQUEST="true")
    request.user = AnonymousUser()

    response = acquisition_login_required(_view)(request)

    assert response.status_code == 204
    assert response["HX-Redirect"].startswith(reverse("account_signup"))
    assert _next_param(response["HX-Redirect"]) == "/somewhere/?a=1"


@pytest.mark.django_db
def test_signups_closed_sends_the_visitor_to_login(mock_site_context, rf):
    SiteSignupPolicyFactory(allow_signups=False)
    request = rf.get("/somewhere/?a=1")
    request.user = AnonymousUser()

    response = acquisition_login_required(_view)(request)

    assert response["Location"].startswith(reverse("account_login"))
    assert _next_param(response["Location"]) == "/somewhere/?a=1"


@pytest.mark.django_db
def test_no_policy_row_follows_the_global_setting(mock_site_context, rf, settings):
    settings.ALLOW_SIGN_UPS = False
    request = rf.get("/somewhere/?a=1")
    request.user = AnonymousUser()

    response = acquisition_login_required(_view)(request)

    assert response["Location"].startswith(reverse("account_login"))


@pytest.mark.django_db
def test_a_view_under_plain_login_required_is_unaffected(mock_site_context, rf):
    request = rf.get("/somewhere/?a=1")
    request.user = AnonymousUser()

    response = login_required(_view)(request)

    assert response["Location"].startswith(reverse("account_login"))
