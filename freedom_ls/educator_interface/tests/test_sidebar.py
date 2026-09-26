"""The educator sidebar: one "Teaching" group and a footer naming the user."""

from __future__ import annotations

import lxml.html
import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture
def sidebar(mock_site_context, logged_in_client):
    """The rendered #sidebar-nav and the whole page, for a logged-in educator."""
    organisation = OrganisationFactory()
    user = UserFactory(
        staff=True, first_name="Ada", last_name="Lovelace", email="ada@example.com"
    )
    assign_object_role(user, organisation, "organisation_staff")
    response = logged_in_client(user).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )
    document = lxml.html.fromstring(response.content)
    (nav,) = document.cssselect("#sidebar-nav")
    return nav, response.content.decode()


@pytest.mark.django_db
def test_sidebar_groups_its_sections_under_a_teaching_heading(sidebar):
    nav, _page = sidebar

    headings = [h.text_content().strip() for h in nav.cssselect("h2")]

    assert headings == ["Teaching"]


@pytest.mark.django_db
def test_sidebar_lists_the_four_sections_each_with_an_icon(sidebar):
    nav, _page = sidebar

    links = nav.cssselect("ul > li > div > a")

    assert [link.text_content().strip() for link in links] == [
        "Dashboard",
        "Cohorts",
        "Learners",
        "Courses",
    ]
    assert all(link.cssselect("svg") for link in links)


@pytest.mark.django_db
def test_sidebar_footer_names_the_signed_in_user(sidebar):
    _nav, page = sidebar

    assert "Ada Lovelace" in page
    assert "ada@example.com" in page
