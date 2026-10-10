"""Tests for the accounts views and the auth pages they render."""

from __future__ import annotations

import re
from html import unescape
from typing import TYPE_CHECKING
from unittest.mock import patch
from urllib.parse import parse_qs, quote_plus, urlparse

import pytest
from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.test import Client, override_settings
from django.urls import reverse

from config import settings_base
from freedom_ls.accounts.decorators import acquisition_login_required
from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.tests._auth_page_helpers import (
    _alert_html,
    _header_html,
    _hrefs_to,
    _next_param,
)
from freedom_ls.accounts.tests._completion_view_fixtures import STORED_PHONE_NUMBERS

if TYPE_CHECKING:
    # Stub-only: the test client's response carries `templates`, which a plain
    # HttpResponse does not.
    from django.test.client import _MonkeyPatchedWSGIResponse


# Tests for the registration-completion view.


PHONE_FORM_PATH = "freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm"


@pytest.fixture
def authed_client(mock_site_context, db):
    user = UserFactory()
    client = Client()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_anonymous_user_redirected_to_login(mock_site_context):
    client = Client()
    response = client.get(reverse("accounts:complete_registration"))
    # login_required redirects to LOGIN_URL with a `next` parameter.
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_user_with_no_incomplete_forms_redirected(authed_client, site, settings):
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[])
    client, _ = authed_client

    response = client.get(reverse("accounts:complete_registration"))

    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_user_with_incomplete_forms_gets_200(authed_client, site):
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    client, _ = authed_client

    response = client.get(reverse("accounts:complete_registration"))

    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "phone_number" in body  # field name leaks via id_for_label / name


@pytest.mark.django_db
def test_posting_valid_data_persists_and_redirects(authed_client, site, settings):
    """The form's `save(user)` must run with `request.user` and persist data."""
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    client, user = authed_client

    response = client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": "+27 11 555 1234"},
    )

    assert response.status_code == 302
    assert response.url == "/"
    user.refresh_from_db()
    # The fixture stores the value on the user via a signal-free save_field.
    assert STORED_PHONE_NUMBERS[user.pk] == "+27 11 555 1234"


@pytest.mark.django_db
def test_posting_invalid_data_re_renders_with_errors(authed_client, site):
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    client, user = authed_client

    response = client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": ""},  # required field empty
    )

    assert response.status_code == 200
    assert user.pk not in STORED_PHONE_NUMBERS


@pytest.mark.django_db
def test_next_param_honored_when_safe(authed_client, site, settings):
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    client, _ = authed_client

    response = client.post(
        reverse("accounts:complete_registration") + "?next=/courses/",
        {
            "PhoneNumberForm-phone_number": "+27 11 555 1234",
            "next": "/courses/",
        },
    )

    assert response.status_code == 302
    assert response.url == "/courses/"


@pytest.mark.django_db
def test_unsafe_next_param_falls_back_to_login_redirect(authed_client, site, settings):
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    client, _ = authed_client

    response = client.post(
        reverse("accounts:complete_registration"),
        {
            "PhoneNumberForm-phone_number": "+27 11 555 1234",
            "next": "https://evil.example.com/phish",
        },
    )

    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_user_id_post_field_is_ignored(authed_client, site, settings):
    """The view always uses `request.user`; a `user_id` POST field is ignored."""
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    client, user = authed_client
    other_user = UserFactory()

    response = client.post(
        reverse("accounts:complete_registration"),
        {
            "PhoneNumberForm-phone_number": "+27 11 555 1234",
            "user_id": str(other_user.pk),
        },
    )
    assert response.status_code == 302

    # The stored phone is for the logged-in user, not the spoofed one.
    assert STORED_PHONE_NUMBERS[user.pk] == "+27 11 555 1234"
    assert other_user.pk not in STORED_PHONE_NUMBERS


@pytest.mark.django_db
def test_post_without_csrf_token_is_rejected(mock_site_context, site, settings):
    """Guards against an accidental CSRF-exemption regression."""
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    user = UserFactory()
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    response = client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": "+27 11 555 1234"},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_get_with_next_renders_hidden_field(authed_client, site):
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    client, _ = authed_client

    response = client.get(reverse("accounts:complete_registration") + "?next=/courses/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="next"' in body
    assert 'value="/courses/"' in body


# The login page names itself and carries a button-weight switch to signup.
#
# An anonymous visitor who lands on `/accounts/login/` should be able to tell,
# at a glance, that this is the login page, and find a prominent way to sign up
# instead if they don't already have an account.


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
    assert _next_param(switch_hrefs[0]) == apply_url


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


# The page django-axes serves once a login attempt is locked out.


# The bare body django-axes returns when no lockout template is configured.
AXES_DEFAULT_BODY = "Account locked: too many login attempts"


def _lock_out(client: Client, email: str) -> _MonkeyPatchedWSGIResponse:
    """Submit failed logins until the pair is locked, and return that response."""
    login_url = reverse("account_login")
    credentials = {
        "login": email,
        "password": "wrong-password",  # pragma: allowlist secret
    }
    responses = [
        client.post(login_url, credentials) for _ in range(settings.AXES_FAILURE_LIMIT)
    ]
    return responses[-1]


@pytest.mark.django_db
def test_lockout_serves_the_branded_page(mock_site_context) -> None:
    user = UserFactory()

    response = _lock_out(Client(), user.email)

    assert response.status_code == 429
    assert "accounts/lockout.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_lockout_renders_the_shared_error_panel(mock_site_context) -> None:
    """Lockout and 429.html must render the same panel."""
    user = UserFactory()

    response = _lock_out(Client(), user.email)

    assert "429 · Account locked" in response.content.decode()


@pytest.mark.django_db
def test_lockout_page_offers_a_route_forward(mock_site_context) -> None:
    """A locked-out visitor must not land on a dead end."""
    user = UserFactory()

    response = _lock_out(Client(), user.email)
    body = response.content.decode()

    assert AXES_DEFAULT_BODY not in body
    assert reverse("account_login") in body
    assert reverse("account_reset_password") in body


@pytest.mark.django_db
def test_lockout_page_promises_the_configured_cool_off(
    mock_site_context, settings
) -> None:
    """The wait the page names must follow AXES_COOLOFF_TIME, not a fixed
    guess: a page that says "a few minutes" beside an hour-long cool-off sends
    the visitor back to a sign-in form that still rejects them.
    """
    settings.AXES_COOLOFF_TIME = 2
    user = UserFactory()

    response = _lock_out(Client(), user.email)

    assert "paused for about 2\xa0hours" in response.content.decode()


# The signup page names itself and carries a button-weight switch to login.
#
# An anonymous visitor who lands on `/accounts/signup/` should be able to tell,
# at a glance, that this is the signup page, and find a prominent way to log in
# instead if they already have an account.


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
    assert _next_param(switch_hrefs[0]) == apply_url


@pytest.mark.django_db
def test_email_from_query_prefills_the_form(mock_site_context):
    response = Client().get(f"{reverse('account_signup')}?email=a@b.example")

    assert 'value="a@b.example"' in response.content.decode()


@pytest.mark.django_db
def test_invalid_email_from_query_is_dropped(mock_site_context):
    response = Client().get(f"{reverse('account_signup')}?email=not-an-email")

    assert "not-an-email" not in response.content.decode()


# Test that signup + email-confirmation flow surfaces Django messages as toasts.
#
# Allauth ships templates for `account/messages/email_confirmation_sent.txt`
# and `account/messages/email_confirmed.txt` and calls `add_message` from
# its email-verification flow. This test guards that those messages reach
# the toast live regions on the post-signup and post-confirm landing pages.


def _assert_toast_body(html: str, region_id: str, expected_text: str) -> None:
    """Assert the response renders a toast in the named region containing `expected_text`."""
    region_marker = f'id="{region_id}"'
    assert region_marker in html, f"region {region_id} missing from response"
    region_start = html.find(region_marker)
    # Take a generous slice — the toast container is the next ~4kB.
    region_slice = html[region_start : region_start + 8000]
    assert '<div id="toast-' in region_slice, (
        f"no toast node in region {region_id}; slice: {region_slice[:500]!r}"
    )
    assert expected_text in region_slice, (
        f"expected '{expected_text}' in toast region {region_id}; slice: {region_slice!r}"
    )


@pytest.mark.django_db(transaction=True)
def test_signup_renders_email_confirmation_toast(mock_site_context) -> None:
    """Post-signup landing page should render an info toast in the polite region."""
    client = Client()
    response = client.post(
        reverse("account_signup"),
        {
            "email": "msg-signup@example.com",  # pragma: allowlist secret
            "password1": "TestPass123!xyz",  # pragma: allowlist secret
            "password2": "TestPass123!xyz",  # pragma: allowlist secret
            "first_name": "Msg",
            "last_name": "Test",
            "accept_terms": "on",
            "accept_privacy": "on",
        },
        follow=True,
    )

    assert response.status_code == 200
    _assert_toast_body(
        response.content.decode(),
        "toast-region-polite",
        "msg-signup@example.com",
    )


@pytest.mark.django_db(transaction=True)
def test_email_confirmation_renders_success_toast(mock_site_context) -> None:
    """Post-confirm landing page should render a success toast in the polite region."""
    client = Client()
    client.post(
        reverse("account_signup"),
        {
            "email": "msg-confirm@example.com",  # pragma: allowlist secret
            "password1": "TestPass123!xyz",  # pragma: allowlist secret
            "password2": "TestPass123!xyz",  # pragma: allowlist secret
            "first_name": "Msg",
            "last_name": "Confirm",
            "accept_terms": "on",
            "accept_privacy": "on",
        },
    )

    email_address = EmailAddress.objects.get(email="msg-confirm@example.com")
    key = EmailConfirmationHMAC(email_address).key
    confirm_url = reverse("account_confirm_email", args=[key])

    response = client.post(confirm_url, follow=True)

    assert response.status_code == 200
    _assert_toast_body(
        response.content.decode(),
        "toast-region-polite",
        "msg-confirm@example.com",
    )


# The post-auth target survives every login/signup link on the auth pages.
#
# An anonymous visitor who is redirected to sign-in or sign-up with a `next`
# target reaches that target after authenticating, however they authenticate —
# whether they use the in-form link or the header's Login/Sign up buttons.


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

    The sign-in page is requested directly: on a site open for signups, apply
    serves an anonymous visitor itself and does not redirect to sign-in.
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
        href: _next_param(href) for href in _hrefs_to(html, "account_signup")
    }

    assert all(v == apply_url for v in next_per_link.values()), next_per_link


@pytest.mark.django_db
def test_every_login_link_on_signup_page_carries_next(signup_page_for_apply):
    apply_url, html = signup_page_for_apply

    next_per_link = {
        href: _next_param(href) for href in _hrefs_to(html, "account_login")
    }

    assert all(v == apply_url for v in next_per_link.values()), next_per_link


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


# Tests for `acquisition_login_required`, the login_required variant that
# sends an anonymous visitor to signup rather than straight to login.


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


# The failure rate limits that sit above the account lockout.
#
# The lockout keys on address and username together, so it never fires on an
# address working through many usernames, nor on many addresses working through
# one account. allauth's `login_failed` limit is what catches both, and these
# tests pin the value and the behaviour.


LOGIN_FAILED_LIMIT = "10/m/ip,5/5m/key"


TOO_MANY_ATTEMPTS = "Too many failed login attempts"


def _post_wrong_password_login(client: Client, email: str):
    return client.post(
        reverse("account_login"),
        {"login": email, "password": "wrong-password"},  # pragma: allowlist secret
    )


def test_login_failed_limit_is_stated_rather_than_inherited() -> None:
    """The value is written out, not left to allauth's computed default.

    Reads settings_base directly: the suite runs under settings_dev, which sets
    ACCOUNT_RATE_LIMITS to False and so carries no limits at all.
    """
    limits = settings_base.ACCOUNT_RATE_LIMITS
    assert isinstance(limits, dict)
    assert limits["login_failed"] == LOGIN_FAILED_LIMIT


def test_deprecated_login_attempts_settings_are_unset() -> None:
    """Defining either one re-derives login_failed and raises a check warning."""
    assert not hasattr(settings, "ACCOUNT_LOGIN_ATTEMPTS_LIMIT")
    assert not hasattr(settings, "ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT")


@pytest.mark.ci_only
@pytest.mark.django_db
def test_failed_logins_from_one_address_are_capped_before_any_lockout(
    mock_site_context,
) -> None:
    """One address working through many usernames is capped, and never locked.

    Eleven failures from one client, each naming a different address, leave every
    address and username pair on one failure, so the lockout cannot fire. The
    eleventh comes back as the login form carrying allauth's own error rather
    than the lockout page.
    """
    cache.clear()
    client = Client()

    with override_settings(ACCOUNT_RATE_LIMITS={"login_failed": LOGIN_FAILED_LIMIT}):
        for attempt in range(10):
            allowed = _post_wrong_password_login(client, f"spray{attempt}@example.com")
            assert TOO_MANY_ATTEMPTS not in allowed.content.decode()

        throttled = _post_wrong_password_login(client, "spray10@example.com")

    body = throttled.content.decode()
    assert TOO_MANY_ATTEMPTS in body
    assert "accounts/lockout.html" not in [
        template.name for template in throttled.templates
    ]


# Integration test that allauth's `ACCOUNT_RATE_LIMITS` actually fires for signup.
#
# Marked `@pytest.mark.ci_only` because the windows are real-time and the
# controlled wall-clock waits make the test too slow for a tight local loop.
# The default local `uv run pytest` invocation excludes `ci_only`. CI must
# include it (e.g. `uv run pytest -m "ci_only or not ci_only"`).
#
# This guards against silent regressions from a typo'd allauth setting key
# or the wrong value-format.


def _post_signup(client: Client, email: str):
    return client.post(
        reverse("account_signup"),
        {
            "email": email,
            "password1": "Sup3rS3cretPass!",  # pragma: allowlist secret
            "password2": "Sup3rS3cretPass!",  # pragma: allowlist secret
            "first_name": "Rate",
            "last_name": "Test",
        },
    )


@pytest.mark.ci_only
@pytest.mark.django_db(transaction=True)
def test_signup_throttles_after_per_ip_limit(mock_site_context):
    """The third signup within the per-IP window is throttled by allauth."""
    client = Client()

    with override_settings(ACCOUNT_RATE_LIMITS={"signup": "2/m/ip"}):
        _post_signup(client, "r0@example.com")
        _post_signup(client, "r1@example.com")
        throttled = _post_signup(client, "r2@example.com")

    # allauth returns HTTP 429 for rate-limited signups.
    assert throttled.status_code == 429


# Sign-up analytics event reaches the landing page after allauth's redirect chain.


@pytest.mark.django_db(transaction=True)
class TestSignUpAnalyticsEventEndToEnd:
    def test_signing_up_emits_the_sign_up_event_on_the_landing_page(
        self, mock_site_context: object
    ) -> None:
        """`save_user` runs before allauth touches the session, and mandatory
        email verification defers login, so the event recorded during signup must
        survive allauth's own redirect chain to the page the new user lands
        on. Guards against a later allauth upgrade changing that chain.
        """
        with (
            override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST"),
            patch("freedom_ls.webhooks.events.attempt_delivery"),
        ):
            response = Client().post(
                reverse("account_signup"),
                {
                    "email": "ga-signup-test@example.com",  # pragma: allowlist secret
                    "password1": "TestPass123!xyz",  # pragma: allowlist secret
                    "password2": "TestPass123!xyz",  # pragma: allowlist secret
                    "first_name": "Ga",
                    "last_name": "Test",
                    "accept_terms": "on",
                    "accept_privacy": "on",
                },
                follow=True,
            )

        assert (
            """gtag('event', 'sign_up', {"method": "email"})"""
            in response.content.decode()
        )
