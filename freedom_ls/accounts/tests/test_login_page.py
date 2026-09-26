"""The login page names itself and carries a button-weight switch to signup.

An anonymous visitor who lands on `/accounts/login/` should be able to tell,
at a glance, that this is the login page, and find a prominent way to sign up
instead if they don't already have an account.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory
from freedom_ls.accounts.tests._auth_page_helpers import _header_html, _hrefs_to


def _title_html(html: str) -> str:
    """The `<title>…</title>` fragment of the page."""
    match = re.search(r"<title.*?</title>", html, re.DOTALL)
    assert match, "page has no <title> element"
    return match.group(0)


@pytest.fixture
def apply_url(course_with_topic):
    course = course_with_topic(access_type="application_gated")
    return reverse("course_applications:apply", kwargs={"course_slug": course.slug})


@pytest.fixture
def login_page(mock_site_context, apply_url):
    response = Client().get(f"{reverse('account_login')}?next={apply_url}")
    return apply_url, response.content.decode()


@pytest.mark.django_db
def test_heading_says_log_in(login_page):
    _, html = login_page

    assert "<h1>Log in</h1>" in html
    assert "Log in" in _title_html(html)


@pytest.mark.django_db
def test_switch_to_signup_is_a_link_labelled_create_an_account(login_page):
    apply_url, html = login_page
    non_header_html = html.replace(_header_html(html), "")

    switch_hrefs = _hrefs_to(non_header_html, "account_signup")

    assert len(switch_hrefs) == 1
    assert "Create an account" in non_header_html
    assert parse_qs(urlparse(switch_hrefs[0]).query).get("next") == [apply_url]


@pytest.mark.django_db
def test_switch_to_signup_is_hidden_when_signups_closed(mock_site_context, apply_url):
    SiteSignupPolicyFactory(allow_signups=False)

    response = Client().get(f"{reverse('account_login')}?next={apply_url}")

    assert _hrefs_to(response.content.decode(), "account_signup") == []


@pytest.mark.django_db
def test_password_reset_link_still_renders(login_page):
    _, html = login_page

    assert _hrefs_to(html, "account_reset_password") != []
