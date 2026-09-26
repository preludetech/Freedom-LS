"""The login page names itself and carries a button-weight switch to signup.

An anonymous visitor who lands on `/accounts/login/` should be able to tell,
at a glance, that this is the login page, and find a prominent way to sign up
instead if they don't already have an account.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, quote_plus, urlparse

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.tests._auth_page_helpers import (
    _alert_html,
    _header_html,
    _hrefs_to,
)


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
def test_switch_to_signup_is_hidden_when_socialaccount_only(
    mock_site_context, apply_url, settings
):
    settings.SOCIALACCOUNT_ONLY = True

    response = Client().get(f"{reverse('account_login')}?next={apply_url}")
    html = response.content.decode()

    assert 'href="None"' not in html
    assert "Create an account" not in html


@pytest.mark.django_db
def test_password_reset_link_still_renders(login_page):
    _, html = login_page

    assert _hrefs_to(html, "account_reset_password") != []


def _post_login(client: Client, *, login: str, password: str, next_url: str):
    return client.post(
        reverse("account_login"),
        {"login": login, "password": password, "next": next_url},
    )


@pytest.mark.django_db
def test_failed_login_shows_the_callout_inside_an_alert(mock_site_context, apply_url):
    response = _post_login(
        Client(),
        login="nobody@example.com",
        password="wrong-password",  # pragma: allowlist secret
        next_url=apply_url,
    )
    alert_html = _alert_html(response.content.decode())

    assert response.status_code == 200
    assert alert_html
    assert "New here?" in alert_html
    assert "Create an account" in alert_html


@pytest.mark.django_db
def test_callout_link_carries_next_and_the_typed_email(mock_site_context, apply_url):
    response = _post_login(
        Client(),
        login="nobody@example.com",
        password="wrong-password",  # pragma: allowlist secret
        next_url=apply_url,
    )
    alert_html = _alert_html(response.content.decode())
    signup_hrefs = _hrefs_to(alert_html, "account_signup")

    assert len(signup_hrefs) == 1
    query = parse_qs(urlparse(signup_hrefs[0]).query)
    assert query.get("next") == [apply_url]
    assert query.get("email") == ["nobody@example.com"]


@pytest.mark.django_db
def test_callout_is_identical_for_a_known_and_an_unknown_email(
    mock_site_context, apply_url
):
    known_email: str = UserFactory().email
    unknown_email = "nobody@example.com"

    known_response = _post_login(
        Client(),
        login=known_email,
        password="wrong-password",  # pragma: allowlist secret
        next_url=apply_url,
    )
    unknown_response = _post_login(
        Client(),
        login=unknown_email,
        password="wrong-password",  # pragma: allowlist secret
        next_url=apply_url,
    )

    known_alert = _alert_html(known_response.content.decode())
    unknown_alert = _alert_html(unknown_response.content.decode())

    assert (
        known_alert.replace(quote_plus(known_email), quote_plus(unknown_email))
        == unknown_alert
    )


@pytest.mark.django_db
def test_callout_shows_on_a_blank_submit(mock_site_context, apply_url):
    response = _post_login(Client(), login="", password="", next_url=apply_url)
    alert_html = _alert_html(response.content.decode())
    signup_hrefs = _hrefs_to(alert_html, "account_signup")

    assert alert_html
    assert "New here?" in alert_html
    assert len(signup_hrefs) == 1
    assert "email" not in parse_qs(urlparse(signup_hrefs[0]).query)


@pytest.mark.django_db
def test_callout_does_not_render_on_a_clean_get(login_page):
    """A pre-existing, always-present toast region also carries role="alert".

    So this checks the alert region nearest the top of the page (ours, when
    the form has errors) rather than every role="alert" on the page.
    """
    _, html = login_page

    assert "New here?" not in _alert_html(html)


@pytest.mark.django_db
def test_callout_is_hidden_when_signups_closed(mock_site_context, apply_url):
    SiteSignupPolicyFactory(allow_signups=False)

    response = _post_login(
        Client(),
        login="nobody@example.com",
        password="wrong-password",  # pragma: allowlist secret
        next_url=apply_url,
    )

    alert_html = _alert_html(response.content.decode())
    assert alert_html
    assert _hrefs_to(alert_html, "account_signup") == []


@pytest.mark.django_db
def test_unusable_email_does_not_break_the_link(mock_site_context, apply_url):
    response = _post_login(
        Client(),
        login='"><script>',
        password="wrong-password",  # pragma: allowlist secret
        next_url=apply_url,
    )
    html = response.content.decode()
    alert_html = _alert_html(html)

    assert "<script>" not in html
    signup_hrefs = _hrefs_to(alert_html, "account_signup")
    assert len(signup_hrefs) == 1
    assert parse_qs(urlparse(signup_hrefs[0]).query).get("email") == ['"><script>']
