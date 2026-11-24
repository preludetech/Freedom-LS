"""The educator interface shell: navigation, breadcrumbs, the interface root and the routes it no longer serves."""

from __future__ import annotations

import lxml.html
import pytest

from django.test import Client
from django.urls import NoReverseMatch, reverse

from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _interface_url,
    _msg_conversation,
    _msg_educator,
    _msg_learner,
    _msg_url,
    messages_section,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
def test_an_instance_page_marks_its_section_current_without_naming_the_instance(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (nav,) = document.cssselect("#sidebar-nav")
    (current,) = nav.cssselect("a[aria-current]")
    assert current.text_content().strip().startswith("Cohorts")
    assert current.get("aria-current") == "true"
    assert "Evening group" not in nav.text_content()


@pytest.mark.django_db
def test_an_instance_page_offers_a_back_link_to_its_list(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (back,) = document.cssselect("#breadcrumbs a")
    assert back.get("href") == _interface_url(organisation.slug, "cohorts")
    assert back.text_content().strip() == "Cohorts"


@pytest.mark.django_db
def test_a_list_page_shows_no_breadcrumb(staff_client: Client):
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    assert not document.cssselect("#breadcrumbs a")
    assert not document.cssselect("#breadcrumbs nav")


@pytest.mark.django_db
def test_navigation_toggle_shows_a_menu_icon_not_a_panel_chevron(
    staff_client: Client,
):
    """The content header's navigation toggle drew a chevron instead of a menu icon."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (toggle,) = document.cssselect("button[aria-label='Open navigation panel']")
    (icon,) = toggle.cssselect("svg")
    assert icon.get("data-icon") == "menu"


@pytest.mark.django_db
def test_navigation_toggle_sits_in_the_page_heading_row(staff_client: Client):
    """On mobile the toggle took a row of its own above the page heading."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (toggle,) = document.cssselect("button[aria-label='Open navigation panel']")
    (heading,) = document.cssselect("#main-content h1")
    assert toggle.getparent() is heading.getparent().getparent()


@pytest.mark.django_db
def test_organisation_root_page_still_offers_the_navigation_toggle(
    staff_client: Client,
):
    """The organisation root used to render a page with no heading of its
    own, leaving a phone with no way to open the navigation. It now sends the
    visitor to a section, and the page they land on offers the toggle."""
    organisation = OrganisationFactory()

    response = staff_client.get(_interface_url(organisation.slug, ""), follow=True)
    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())

    (toggle,) = document.cssselect(
        "#main-content button[aria-label='Open navigation panel']"
    )
    assert toggle.cssselect("svg[data-icon]")


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_a_cohort_role_holder_sees_no_administration_group(role_holder_client, role):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, role)

    document = _get_document(client, _interface_url(organisation.slug, "cohorts"))

    headings = [h.text_content().strip() for h in document.cssselect("#sidebar-nav h2")]
    assert headings == ["Teaching"]


@pytest.mark.django_db
def test_a_cohort_admin_still_sees_the_dashboard(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, "cohort_admin")

    response = client.get(_interface_url(organisation.slug, ""))

    assert response.status_code == 302
    assert response["Location"] == _interface_url(organisation.slug, "dashboard")


# The educator interface has no Messages section: the conversation with a
# learner lives on the learner page.


@pytest.mark.django_db
@messages_section
@pytest.mark.parametrize("messaging_enabled", [True, False])
def test_the_messages_section_paths_are_404s(
    msg_client_for, settings, messaging_enabled
):
    settings.MESSAGING_ENABLED = messaging_enabled
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)
    conversation = _msg_conversation(educator, learner.user)
    client = msg_client_for(educator)

    assert client.get(_msg_url(organisation, "messages")).status_code == 404
    assert (
        client.get(_msg_url(organisation, f"messages/{conversation.pk}")).status_code
        == 404
    )


def test_the_unread_count_route_no_longer_exists():
    with pytest.raises(NoReverseMatch):
        reverse(
            "educator_interface:messages_unread_count",
            kwargs={"organisation_slug": "any"},
        )
