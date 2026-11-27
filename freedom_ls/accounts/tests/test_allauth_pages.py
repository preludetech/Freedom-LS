"""Tests for allauth's account-management pages: the email and password pages
redirect to Personal details, and the remaining ones render in the account
shell shaped like the panel pages."""

from __future__ import annotations

from typing import cast

import lxml.html
import pytest
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.template import Engine, RequestContext, Template
from django.template.base import Origin
from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User

SHELL_HOSTS = [
    "interface-main",
    "app-modal",
    "app-modal-body",
    "quick-view",
    "scope-announcer",
]

# A management page as allauth writes one: a heading element, then a form
# element with a body and a submit button among its actions.
STUB_MANAGE_PAGE = """{% extends "allauth/layouts/manage.html" %}{% load allauth %}
{% block head_title %}Sessions{% endblock head_title %}
{% block content %}
    {% element h1 %}Sessions{% endelement %}
    {% element form method="post" action="/stub/" %}
        {% slot body %}<p>Your signed-in sessions.</p>{% endslot %}
        {% slot actions %}{% element button type="submit" %}Sign out the others{% endelement %}{% endslot %}
    {% endelement %}
{% endblock content %}
"""


@pytest.fixture
def signed_in(db: None, mock_site_context: Site) -> tuple[Client, User]:
    user = cast(User, UserFactory())
    EmailAddress.objects.create(
        user=user, email=user.email, primary=True, verified=True
    )
    client = Client()
    client.force_login(user)
    return client, user


@pytest.mark.parametrize("url_name", ["account_email", "account_change_password"])
def test_the_email_and_password_pages_redirect_to_personal_details(
    signed_in: tuple[Client, User], url_name: str
) -> None:
    client, _ = signed_in

    response = client.get(reverse(url_name))

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "accounts:account_profile", kwargs={"path_string": "personal-details"}
    )


def test_the_set_password_page_still_answers_for_a_user_with_no_password(
    signed_in: tuple[Client, User],
) -> None:
    """A claimed application sends its new user here with a `next`."""
    client, user = signed_in
    user.set_unusable_password()
    user.save()
    client.force_login(user)

    response = client.get(reverse("account_set_password"), {"next": "/somewhere/"})

    html = response.content.decode()
    assert response.status_code == 200
    assert 'id="sidebar-nav"' in html
    assert "data-page-header" in html


def test_reauthenticate_page_has_no_account_sidebar(
    signed_in: tuple[Client, User],
) -> None:
    client, _ = signed_in

    response = client.get(reverse("account_reauthenticate"))

    assert response.status_code == 200
    assert 'id="sidebar-nav"' not in response.content.decode()


@pytest.fixture
def stub_manage_page(signed_in: tuple[Client, User]) -> lxml.html.HtmlElement:
    _, user = signed_in
    request = RequestFactory().get("/stub/")
    request.user = user
    # allauth reads the layout from the template names in the extends chain,
    # so the stub needs a name of its own.
    template = Template(
        STUB_MANAGE_PAGE,
        origin=Origin(name="stub_manage_page.html", template_name="stub.html"),
        engine=Engine.get_default(),
    )
    html = template.render(RequestContext(request))
    return lxml.html.fromstring(html)


def test_a_management_page_renders_in_the_account_shell(
    stub_manage_page: lxml.html.HtmlElement,
) -> None:
    assert stub_manage_page.cssselect('nav#sidebar-nav[aria-label="Account"]')
    for host in SHELL_HOSTS:
        assert stub_manage_page.get_element_by_id(host) is not None


def test_a_management_page_puts_the_toggle_in_the_heading_row(
    stub_manage_page: lxml.html.HtmlElement,
) -> None:
    (toggle,) = stub_manage_page.cssselect('button[aria-label="Open navigation panel"]')
    (heading,) = stub_manage_page.cssselect("#interface-main h1")

    assert toggle.getparent() is heading.getparent()
    assert heading.text_content().strip() == "Sessions"
    band = toggle.getparent().getparent()
    assert band.get("data-page-header") is not None
    assert "panel-surface" in band.get("class").split()


def test_a_management_page_sits_on_the_panel_canvas(
    stub_manage_page: lxml.html.HtmlElement,
) -> None:
    main = stub_manage_page.get_element_by_id("interface-main")

    assert "panel-canvas" in main.get("class").split()


def test_a_management_page_form_is_a_card_with_its_buttons_in_the_footer(
    stub_manage_page: lxml.html.HtmlElement,
) -> None:
    (form,) = stub_manage_page.cssselect('form[action="/stub/"]')
    (card,) = form.cssselect(".panel-surface")
    (submit,) = form.cssselect('button[type="submit"]')

    assert "Your signed-in sessions." in card.text_content()
    assert submit.getparent().tag == "footer" or any(
        ancestor.tag == "footer" for ancestor in submit.iterancestors()
    )
    assert "btn-sm" in submit.get("class").split()


def test_the_sign_out_page_puts_its_card_inside_a_full_width_canvas_region(
    signed_in: tuple[Client, User],
) -> None:
    """The sign out card used to be a direct child of the content column, so
    the header band and the content began at different x positions. It now
    sits inside a canvas wrapper that carries the gutter, as the personal
    details page does, and the question and the button share one card."""
    client, _user = signed_in

    response = client.get(reverse("account_logout"))

    assert response.status_code == 200
    page = lxml.html.fromstring(response.content.decode())
    main = page.get_element_by_id("interface-main")
    children = [child for child in main if child.tag == "div"]
    band, *rest = children
    assert band.get("data-page-header") is not None
    (form,) = main.cssselect("form[action$='/logout/']")
    assert form.getparent() is not main
    (canvas,) = [child for child in rest if form in child.iterdescendants()]
    assert "panel-canvas" in canvas.get("class").split()
    (card,) = form.cssselect(".panel-surface")
    assert "Are you sure you want to sign out?" in card.text_content()
    assert card.cssselect('button[type="submit"]')
