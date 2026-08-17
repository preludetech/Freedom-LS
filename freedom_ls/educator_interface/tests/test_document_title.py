"""The educator interface names the current page in the browser tab.

Two paths have to agree. A full page load renders the <title> through the base
template, while moving around inside the interface is an out-of-band fragment
swap that never reloads the page — so navigation has to carry a <title> of its
own, in the same format, or the tab goes stale after the first click.
"""

from __future__ import annotations

from typing import cast

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


@pytest.fixture
def cohorts_page(logged_in_client) -> tuple[Client, str, Organisation]:
    """An educator logged in against one organisation, plus its cohorts URL."""
    organisation = cast(Organisation, OrganisationFactory(name="Northside Academy"))
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_staff")
    url = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
    )
    return logged_in_client(educator), url, organisation


def _title_text(html: str) -> str:
    """The text inside the response's <title> element, whitespace stripped."""
    return html.split("<title>")[1].split("</title>")[0].strip()


@pytest.mark.django_db
def test_full_page_load_titles_the_tab_with_page_organisation_and_site(
    cohorts_page, mock_site_context
):
    client, url, organisation = cohorts_page

    response = client.get(url)

    assert response.status_code == 200
    title = _title_text(response.content.decode())
    assert title == f"Cohorts — {organisation.name} — {mock_site_context.name}"


@pytest.mark.django_db
def test_htmx_navigation_response_carries_a_title_element(cohorts_page):
    client, url, _organisation = cohorts_page

    response = client.get(url, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="main-content")

    assert response.status_code == 200
    assert "<title>" in response.content.decode()


@pytest.mark.django_db
def test_htmx_navigation_title_matches_the_full_page_title(cohorts_page):
    client, url, _organisation = cohorts_page

    full_page = client.get(url)
    navigation = client.get(url, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="main-content")

    assert _title_text(navigation.content.decode()) == _title_text(
        full_page.content.decode()
    )
