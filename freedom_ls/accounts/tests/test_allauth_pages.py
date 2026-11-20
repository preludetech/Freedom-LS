"""Tests for allauth's account-management pages inside the account shell."""

from __future__ import annotations

import re

import pytest
from allauth.account.models import EmailAddress

from django.contrib import messages
from django.contrib.messages.storage import default_storage
from django.http import HttpResponse
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory

SHELL_HOSTS = [
    'id="interface-main"',
    'id="app-modal"',
    'id="app-modal-body"',
    'id="quick-view"',
    'id="scope-announcer"',
]


@pytest.fixture
def signed_in(db, mock_site_context):
    user = UserFactory()
    EmailAddress.objects.create(
        user=user, email=user.email, primary=True, verified=True
    )
    client = Client()
    client.force_login(user)
    return client, user


def _current_entry_hrefs(html: str) -> list[str]:
    nav = re.search(r'<nav id="sidebar-nav".*?</nav>', html, re.DOTALL)
    assert nav, "page has no account sidebar"
    return re.findall(r'<a href="([^"]*)"\s+aria-current="page"', nav.group(0))


@pytest.mark.parametrize(
    "url_name",
    ["account_email", "account_change_password", "account_set_password"],
)
def test_management_page_renders_in_the_account_shell(signed_in, url_name):
    client, user = signed_in
    if url_name == "account_set_password":
        user.set_unusable_password()
        user.save()
        client.force_login(user)
    elif url_name == "account_change_password":
        user.set_password("a-long-passphrase-1")
        user.save()
        client.force_login(user)

    response = client.get(reverse(url_name))
    html = response.content.decode()

    assert response.status_code == 200
    assert 'aria-label="Account"' in html
    assert len(_current_entry_hrefs(html)) == 1
    for host in SHELL_HOSTS:
        assert host in html
    assert html.count('aria-label="Open navigation panel"') == 1
    assert "<h1" in html


def test_success_message_on_the_email_page_renders_as_a_toast(signed_in):
    client, _ = signed_in
    request = client.get(reverse("account_email")).wsgi_request
    storage = default_storage(request)
    storage.add(messages.SUCCESS, "Primary email address set.")
    response = HttpResponse()
    storage.update(response)
    for name, morsel in response.cookies.items():
        client.cookies[name] = morsel

    html = client.get(reverse("account_email")).content.decode()

    assert "Primary email address set." in html
    assert "toast-region-polite" in html


def test_reauthenticate_page_has_no_account_sidebar(signed_in):
    client, _ = signed_in

    response = client.get(reverse("account_reauthenticate"))

    assert response.status_code == 200
    assert 'id="sidebar-nav"' not in response.content.decode()


def test_management_page_navigation_toggle_is_not_in_a_centred_wrapper(signed_in):
    """The toggle used to sit in a centred max-w-7xl wrapper inside the narrow column.

    That wrapper shrank to fit and centred itself, so the toggle sat well to
    the right of the page's own heading below the lg breakpoint.
    """
    client, _ = signed_in

    html = client.get(reverse("account_email")).content.decode()
    main = html[html.index('id="interface-main"') : html.index("<footer")]

    assert "max-w-7xl" not in main
    assert "mx-auto" not in main[: main.index("<h1")]
    assert main.count('aria-label="Open navigation panel"') == 1
