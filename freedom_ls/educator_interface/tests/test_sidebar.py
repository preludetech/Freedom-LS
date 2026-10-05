"""The educator sidebar: one "Teaching" group and a footer naming the user."""

from __future__ import annotations

from collections.abc import Callable

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture
def sidebar(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> tuple[lxml.html.HtmlElement, str]:
    """The rendered #sidebar-nav and the whole page, for a logged-in educator."""
    organisation = OrganisationFactory()
    user = UserFactory(
        staff=True, first_name="Ada", last_name="Lovelace", email="ada@example.com"
    )
    assign_object_role(user, organisation, "organisation_admin")
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
def test_sidebar_groups_its_sections_under_a_teaching_heading(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    headings = [h.text_content().strip() for h in nav.cssselect("h2")]

    assert headings == ["Teaching"]


@pytest.mark.django_db
def test_sidebar_lists_the_four_sections_each_with_an_icon(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
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
def test_sidebar_footer_names_the_signed_in_user(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    _nav, page = sidebar

    assert "Ada Lovelace" in page
    assert "ada@example.com" in page


@pytest.mark.django_db
def test_user_block_follows_the_nav_inside_the_sidebar_dialog(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar
    dialog = nav.xpath("ancestor::dialog[@aria-label='Navigation']")[0]

    (user_block,) = dialog.cssselect("#sidebar-user")

    assert user_block.getparent() is nav.getparent()
    assert nav in user_block.itersiblings(preceding=True)


@pytest.mark.django_db
def test_navigation_dialog_has_a_close_button_before_the_organisation_switcher(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar
    dialog = nav.xpath("ancestor::dialog[@aria-label='Navigation']")[0]

    (close_button,) = dialog.xpath(".//button[@aria-label='Close navigation']")
    (switcher,) = dialog.cssselect("#organisation-switcher")

    document_order = list(dialog.iter())
    assert document_order.index(close_button) < document_order.index(switcher)


@pytest.mark.django_db
def test_nav_links_are_not_underlined(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    links = nav.cssselect("a")

    assert links
    assert all("no-underline" in link.get("class") for link in links)


@pytest.mark.django_db
def test_the_active_item_draws_a_rounded_primary_bar_on_a_tinted_fill(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar

    (active,) = [a for a in nav.cssselect("a") if a.get("aria-current") == "page"]

    classes = active.get("class")
    assert "aria-[current=page]:bg-surface-2" in classes
    assert "aria-[current=page]:text-primary" in classes
    assert "aria-[current=page]:shadow-[inset_2px_0_0_var(--color-primary)]" in classes
    assert "border-l" not in classes


@pytest.mark.django_db
def test_the_user_block_shows_an_initials_avatar_the_name_the_email_and_a_settings_link(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar
    dialog = nav.xpath("ancestor::dialog[@aria-label='Navigation']")[0]

    (user_block,) = dialog.cssselect("#sidebar-user")

    (avatar,) = user_block.cssselect("[aria-hidden='true'].rounded-full")
    assert avatar.text_content().strip() == "AL"
    assert "Ada Lovelace" in user_block.text_content()
    assert "ada@example.com" in user_block.text_content()
    (settings_link,) = user_block.cssselect("a[aria-label='Account settings']")
    assert settings_link.get("href") == reverse("accounts:account_profile")
    assert settings_link.cssselect("svg")


@pytest.mark.django_db
def test_the_rule_above_the_user_block_runs_the_full_sidebar_width(
    sidebar: tuple[lxml.html.HtmlElement, str],
) -> None:
    nav, _page = sidebar
    dialog = nav.xpath("ancestor::dialog[@aria-label='Navigation']")[0]

    (user_block,) = dialog.cssselect("#sidebar-user")

    classes = user_block.get("class")
    assert "border-t" in classes
    assert "-mx-4" in classes
    assert "lg:-mx-6" in classes


@pytest.mark.django_db
def test_a_user_with_no_name_shows_their_email_once(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(
        staff=True, first_name="", last_name="", email="nameless@example.com"
    )
    assign_object_role(user, organisation, "organisation_admin")
    response = logged_in_client(user).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )

    (user_block,) = lxml.html.fromstring(response.content).cssselect("#sidebar-user")

    assert user_block.text_content().count("nameless@example.com") == 1
    (avatar,) = user_block.cssselect("[aria-hidden='true'].rounded-full")
    assert avatar.text_content().strip() == "NA"
