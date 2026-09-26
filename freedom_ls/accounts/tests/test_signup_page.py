"""The signup page names itself and carries a button-weight switch to login.

An anonymous visitor who lands on `/accounts/signup/` should be able to tell,
at a glance, that this is the signup page, and find a prominent way to log in
instead if they already have an account.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest

from django.test import Client
from django.urls import reverse

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
def signup_page(mock_site_context, apply_url):
    response = Client().get(f"{reverse('account_signup')}?next={apply_url}")
    return apply_url, response.content.decode()


@pytest.mark.django_db
def test_heading_says_create_an_account(signup_page):
    _, html = signup_page

    assert "<h1>Create an account</h1>" in html
    assert "Create an account" in _title_html(html)


@pytest.mark.django_db
def test_switch_to_login_is_a_link_labelled_log_in(signup_page):
    apply_url, html = signup_page
    non_header_html = html.replace(_header_html(html), "")

    switch_hrefs = _hrefs_to(non_header_html, "account_login")

    assert len(switch_hrefs) == 1
    assert "Log in" in non_header_html
    assert parse_qs(urlparse(switch_hrefs[0]).query).get("next") == [apply_url]


@pytest.mark.django_db
def test_email_from_query_prefills_the_form(mock_site_context):
    response = Client().get(f"{reverse('account_signup')}?email=a@b.example")

    assert 'value="a@b.example"' in response.content.decode()


@pytest.mark.django_db
def test_invalid_email_from_query_is_dropped(mock_site_context):
    response = Client().get(f"{reverse('account_signup')}?email=not-an-email")

    assert "not-an-email" not in response.content.decode()
