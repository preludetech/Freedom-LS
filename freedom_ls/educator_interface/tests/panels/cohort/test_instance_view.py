"""The cohort page: its tab set, header and overview: educator_interface/panels/cohort/instance_view.py."""

from __future__ import annotations

from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.educator_interface.events import COHORT_CHANGED
from freedom_ls.educator_interface.tests.helpers import (
    _add_member,
    _cohort_page,
    _get_document,
    _header_of,
    _interface_url,
)
from freedom_ls.educator_interface.tests.interface_walk import (
    WalkedPanel,
    walk_interface,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
def test_cohort_detail_page_has_overview_learners_courses_report_settings_and_history_tabs(
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
        "overview",
        "learners",
        "courses",
        "report",
        "settings",
        "history",
    ]
    assert links[0].get("aria-current") == "page"
    assert links[1].get("aria-current") is None
    assert links[1].text_content().split() == ["Learners", "2"]
    headings = [
        h.text_content().strip() for h in document.cssselect("[data-tab-set] h2")
    ]
    assert headings == [
        "Details",
        "Course completion",
        "Needs attention",
    ]


@pytest.mark.django_db
def test_the_learners_tab_count_excludes_a_removed_member(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )
    CohortMembershipFactory(
        cohort=cohort,
        learner=LearnerFactory(organisation=organisation, is_active=False),
    )

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    assert nav.cssselect("a")[1].text_content().split() == ["Learners", "1"]


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
    assert not header.cssselect("button[hx-get]")
    (details_panel,) = document.cssselect("section[data-panel='details']")
    assert not details_panel.cssselect("footer")
    assert not details_panel.cssselect("button[hx-get]")

    settings = _get_document(staff_client, f"{page_url}/__tabs/settings")

    triggers = {button.get("hx-get") for button in settings.cssselect("button[hx-get]")}
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/deactivate" in triggers
    )
    assert f"{page_url}/__tabs/settings/__panels/name/__actions/edit" not in triggers
    (form,) = settings.cssselect("form#cohort-name-form")
    assert (
        form.get("hx-post")
        == f"{page_url}/__tabs/settings/__panels/name/__actions/edit"
    )
    (name,) = form.cssselect("input[name=name]")
    assert name.get("value") == "Evening group"
    assert name.get("autofocus") is None
    assert all(
        "btn-sm" in button.get("class").split()
        for button in settings.cssselect("section[data-panel='status'] footer .btn")
    )


@pytest.mark.django_db
def test_settings_tab_is_present_for_an_organisation_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, admin, "organisation_admin", organisation)

    document = _get_document(
        logged_in_client(admin),
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}"),
    )

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    assert "Settings" in [a.text_content().split()[0] for a in nav.cssselect("a")]


@pytest.mark.django_db
def test_settings_tab_answers_404_for_a_cohort_viewer(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_viewer", cohort)

    response = logged_in_client(educator).get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/settings")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_active_cohort_header_has_no_badge_no_stats_and_no_buttons(
    staff_client: Client,
):
    """Active is the default, the tabs already count learners and courses, and
    the actions live in Settings, so the header is the name and the tabs."""
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)

    header = _header_of(_cohort_page(staff_client, cohort))

    assert "Active" not in header.text_content()
    assert "Learners" not in header.text_content()
    assert not header.cssselect(".btn")


@pytest.mark.django_db
def test_inactive_cohort_header_shows_the_inactive_badge(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)

    document = _cohort_page(staff_client, cohort)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    assert "Inactive" in header.text_content().split()


@pytest.mark.django_db
def test_cohort_header_refreshes_its_counts_when_the_cohort_changes(
    staff_client: Client,
):
    """The header stats and tab counts stayed stale after a membership change
    because nothing re-fetched them when the cohort-changed event fired."""
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    (refresher,) = document.cssselect("#instance-header [data-refresh-events]")
    assert refresher.get("data-refresh-events") == COHORT_CHANGED


@pytest.mark.django_db
def test_a_header_refresh_gets_the_header_alone(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)

    response = staff_client.get(
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}"),
        headers={"HX-Request": "true", "HX-Target": "instance-header"},
    )

    document = lxml.html.fromstring(response.content.decode())
    assert (
        document.get("id"),
        len(document.cssselect("[data-panel]")),
    ) == ("instance-header", 0)


@pytest.mark.django_db
def test_the_cohort_page_opens_on_the_overview_tab(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    (active,) = [a for a in nav.cssselect("a") if a.get("aria-current") == "page"]
    assert active.text_content().split()[0] == "Overview"


@pytest.mark.django_db
def test_overview_lists_details_completion_and_attention_in_order(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    panels = [
        s.get("data-panel")
        for s in document.cssselect("[data-tab-set] section[data-panel]")
    ]
    assert panels[:3] == ["details", "completion", "attention"]


@pytest.mark.django_db
def test_every_panel_under_the_cohort_page_refreshes_on_cohort_changed(
    mock_site_context: Site,
):
    organisation = OrganisationFactory()
    cohort_paths = [
        item
        for item in walk_interface(organisation)
        if isinstance(item, WalkedPanel)
        and item.path.startswith("cohorts/")
        and "/__" in item.path
        and "/__actions/" not in item.path
    ]

    missing = [
        item.path
        for item in cohort_paths
        if COHORT_CHANGED not in item.panel.refresh_events
    ]

    assert cohort_paths
    assert missing == []
