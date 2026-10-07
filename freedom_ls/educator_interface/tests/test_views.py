"""The educator interface's section configs and the pages they render."""

from __future__ import annotations

import lxml.html
import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


def _get_document(client: Client, url: str) -> lxml.html.HtmlElement:
    response = client.get(url)
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


@pytest.mark.django_db
def test_cohort_detail_page_has_a_details_tab_and_a_learners_tab(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    for _ in range(2):
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    links = nav.cssselect("a")
    assert [link.get("href").rsplit("/", 1)[-1] for link in links] == [
        "details",
        "learners",
    ]
    assert links[0].get("aria-current") == "page"
    assert links[1].get("aria-current") is None
    assert links[1].text_content().split() == ["Learners", "2"]
    headings = [h.text_content().strip() for h in document.cssselect("h2")]
    assert "Details" in headings
    assert "Course Registrations" in headings
    assert "Learners" not in headings


@pytest.mark.django_db
def test_the_learners_tab_url_renders_the_cohorts_learners(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    CohortMembershipFactory(cohort=cohort, learner=learner)

    document = _get_document(
        staff_client,
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"),
    )

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    (active,) = [a for a in nav.cssselect("a") if a.get("aria-current") == "page"]
    assert active.text_content().split()[0] == "Learners"
    (region,) = document.cssselect("[data-tab-set]")
    assert "Lovelace" in region.text_content()
    assert "Course Registrations" not in region.text_content()


@pytest.mark.django_db
def test_cohort_page_actions_sit_in_the_page_header_not_the_details_card(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    page_url = _interface_url(organisation.slug, f"cohorts/{cohort.pk}")

    document = _get_document(staff_client, page_url)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    triggers = {button.get("hx-get") for button in header.cssselect("button[hx-get]")}
    assert triggers == {f"{page_url}/__actions/edit", f"{page_url}/__actions/delete"}
    (details_panel,) = document.cssselect("section[data-panel='details']")
    assert not details_panel.cssselect("footer")
    assert not details_panel.cssselect("button[hx-get]")


@pytest.mark.django_db
def test_learner_detail_page_is_titled_with_the_learners_name_not_the_user_str(
    staff_client: Client,
):
    organisation = OrganisationFactory(name="Northside")
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="Ada",
        user__last_name="Lovelace",
        user__email="ada@example.com",
    )

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"learners/{learner.pk}")
    )

    (heading,) = document.cssselect("#instance-title")
    assert heading.text_content().strip() == "Ada Lovelace"
    assert "ada@example.com - Northside" not in lxml.html.tostring(
        document, encoding="unicode"
    )


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
