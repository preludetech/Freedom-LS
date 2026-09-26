"""The post-auth target survives every login/signup link on the auth pages.

An anonymous visitor who is redirected to sign-in or sign-up with a `next`
target reaches that target after authenticating, however they authenticate —
whether they use the in-form link or the header's Login/Sign up buttons.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, urlparse

import pytest
from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.tests._auth_page_helpers import _header_html, _hrefs_to


def _signup_via(client: Client, signup_href: str, email: str) -> str:
    """Sign up from `signup_href`, confirm the email and return the landing path."""
    signup_page = client.get(signup_href)
    next_values = re.findall(
        r'name="next"[^>]*value="([^"]*)"', signup_page.content.decode()
    )
    payload = {
        "email": email,
        "password1": "TestPass123!xyz",  # pragma: allowlist secret
        "password2": "TestPass123!xyz",  # pragma: allowlist secret
        "first_name": "Signup",
        "last_name": "Visitor",
        "accept_terms": "on",
        "accept_privacy": "on",
    }
    if next_values:
        payload["next"] = unescape(next_values[0])
    client.post(signup_href, payload)

    token = EmailConfirmationHMAC(EmailAddress.objects.get(email=email))
    confirmed = client.post(
        reverse("account_confirm_email", args=[token.key]), follow=False
    )
    return confirmed["Location"]


@pytest.fixture
def login_page_for_apply(mock_site_context, course_with_topic):
    """The sign-in page reached directly with a pending apply-page `next`.

    Apply itself now sends an anonymous visitor to signup (see
    test_acquisition_login_required.py), so this fixture reaches the sign-in
    page the way the header's own Login link and a closed-signups site would:
    directly, with `next` already set to the apply URL.
    """
    course = course_with_topic(access_type="application_gated")
    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    client = Client()
    login_page = client.get(f"{reverse('account_login')}?next={apply_url}")
    return client, apply_url, login_page.content.decode()


@pytest.fixture
def signup_page_for_apply(mock_site_context, course_with_topic):
    """The sign-up page reached directly with a pending apply-page `next`."""
    course = course_with_topic(access_type="application_gated")
    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    client = Client()
    signup_page = client.get(f"{reverse('account_signup')}?next={apply_url}")
    return apply_url, signup_page.content.decode()


@pytest.mark.django_db
def test_login_page_offers_two_signup_links(login_page_for_apply):
    _, _, html = login_page_for_apply

    assert len(_hrefs_to(html, "account_signup")) == 2


@pytest.mark.django_db
def test_every_signup_link_on_login_page_carries_next(login_page_for_apply):
    _, apply_url, html = login_page_for_apply

    next_per_link = {
        href: parse_qs(urlparse(href).query).get("next")
        for href in _hrefs_to(html, "account_signup")
    }

    assert all(v == [apply_url] for v in next_per_link.values()), next_per_link


@pytest.mark.django_db
def test_every_login_link_on_signup_page_carries_next(signup_page_for_apply):
    apply_url, html = signup_page_for_apply

    next_per_link = {
        href: parse_qs(urlparse(href).query).get("next")
        for href in _hrefs_to(html, "account_login")
    }

    assert all(v == [apply_url] for v in next_per_link.values()), next_per_link


@pytest.mark.django_db(transaction=True)
def test_in_form_signup_link_lands_on_apply_page(login_page_for_apply):
    client, apply_url, html = login_page_for_apply
    non_header_html = html.replace(_header_html(html), "")
    in_form_link = _hrefs_to(non_header_html, "account_signup")[0]

    landing = _signup_via(client, in_form_link, "in-form@example.com")

    assert landing == apply_url


@pytest.mark.django_db(transaction=True)
def test_header_signup_link_lands_on_apply_page(login_page_for_apply):
    client, apply_url, html = login_page_for_apply
    header_link = _hrefs_to(_header_html(html), "account_signup")[0]

    landing = _signup_via(client, header_link, "header@example.com")

    assert landing == apply_url
