"""The learner page: educator_interface/panels/learner/instance_view.py.

Its title, header badge, tab set and where each action sits across the tabs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import lxml.html
import pytest

from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.events import LEARNER_CHANGED
from freedom_ls.educator_interface.tests.helpers import (
    _add_member,
    _get_document,
    _header_of,
    _interface_url,
    _learner_page,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper


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
def test_an_active_learner_header_has_no_badge_and_no_buttons(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, user__first_name="Ada")

    header = _header_of(
        _get_document(
            staff_client, _interface_url(organisation.slug, f"learners/{learner.pk}")
        )
    )

    assert not header.cssselect(".chip")
    assert not header.cssselect(".btn")


@pytest.mark.django_db
def test_an_inactive_learner_header_shows_the_inactive_badge(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    header = _header_of(
        _get_document(
            staff_client, _interface_url(organisation.slug, f"learners/{learner.pk}")
        )
    )

    (badge,) = header.cssselect(".chip")
    assert badge.text_content().strip() == "Inactive"


@pytest.mark.django_db
def test_add_to_cohort_sits_under_the_learners_cohorts_panel(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    document = _get_document(staff_client, page_url)

    (panel,) = document.cssselect("section[data-panel='cohorts']")
    labels = [
        button.text_content().strip() for button in panel.cssselect("footer .btn")
    ]
    assert labels == ["Add to cohort"]


@pytest.mark.django_db
def test_the_learners_cohorts_table_shows_as_cards_when_its_panel_is_narrow(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(
        cohort=CohortFactory(organisation=organisation), learner=learner
    )
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    document = _get_document(staff_client, page_url)

    (panel,) = document.cssselect("section[data-panel='cohorts']")
    (wrapper,) = panel.cssselect("[data-table-layout]")
    (region,) = wrapper.cssselect("[role='region']")
    (cards,) = wrapper.xpath("./ul")
    assert "@container" in wrapper.get("class", "").split()
    assert "@min-[58rem]:block" in region.get("class", "").split()
    assert "@min-[58rem]:hidden" in cards.get("class", "").split()


@pytest.mark.django_db
def test_a_cohort_admin_gets_the_cohort_and_course_actions_but_no_settings_tab(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    learner = _add_member(cohort)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    client = logged_in_client(educator)
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    overview = _get_document(client, page_url)
    courses = _get_document(client, f"{page_url}/__tabs/courses")

    (cohorts_panel,) = overview.cssselect("section[data-panel='cohorts']")
    assert [
        b.text_content().strip() for b in cohorts_panel.cssselect("footer .btn")
    ] == ["Add to cohort"]
    (courses_panel,) = courses.cssselect("section[data-panel='courses']")
    assert [
        b.text_content().strip() for b in courses_panel.cssselect("footer .btn")
    ] == ["Register for a course"]
    assert not overview.cssselect("a[href$='/__tabs/settings']")


@pytest.mark.django_db
def test_the_learner_settings_tab_is_hidden_from_a_cohort_viewer(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    learner = _add_member(cohort)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_viewer", cohort)
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")
    client = logged_in_client(educator)

    document = _get_document(client, page_url)

    (nav,) = document.cssselect("nav[aria-label='Learner sections']")
    assert "Settings" not in [a.text_content().split()[0] for a in nav.cssselect("a")]
    assert client.get(f"{page_url}/__tabs/settings").status_code == 404


@pytest.mark.django_db
def test_the_learner_header_refreshes_on_learner_changed(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"learners/{learner.pk}")
    )

    (refresher,) = document.cssselect("#instance-header [data-refresh-events]")
    assert refresher.get("data-refresh-events") == LEARNER_CHANGED


@pytest.mark.django_db
@pytest.mark.usefixtures("_messaging_on")
def test_the_learner_page_has_overview_courses_messages_and_history_tabs(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())

    document = _learner_page(staff_client, learner)

    (nav,) = document.cssselect("nav[aria-label='Learner sections']")
    links = nav.cssselect("a")
    assert [link.get("href").rsplit("/", 1)[-1] for link in links] == [
        "overview",
        "courses",
        "messages",
        "settings",
        "history",
    ]


@pytest.mark.django_db
def test_the_learner_page_has_no_messages_tab_when_messaging_is_off(
    staff_client: Client, settings: SettingsWrapper
):
    settings.MESSAGING_ENABLED = False
    learner = LearnerFactory(organisation=OrganisationFactory())

    document = _learner_page(staff_client, learner)

    (nav,) = document.cssselect("nav[aria-label='Learner sections']")
    links = nav.cssselect("a")
    assert [link.get("href").rsplit("/", 1)[-1] for link in links] == [
        "overview",
        "courses",
        "settings",
        "history",
    ]


@pytest.mark.django_db
def test_the_learner_page_opens_on_the_overview_tab(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())

    document = _learner_page(staff_client, learner)

    (nav,) = document.cssselect("nav[aria-label='Learner sections']")
    (active,) = [a for a in nav.cssselect("a") if a.get("aria-current") == "page"]
    assert active.text_content().split()[0] == "Overview"


@pytest.mark.django_db
def test_the_learner_header_carries_the_email_subtitle_and_no_active_badge(
    staff_client: Client,
):
    learner = LearnerFactory(
        organisation=OrganisationFactory(), user__email="ada@example.com"
    )

    document = _learner_page(staff_client, learner)

    (title,) = document.cssselect("#instance-title")
    header = title.xpath("ancestor::div[contains(@class, 'justify-between')][1]")[0]
    assert "Active" not in header.text_content()
    assert "ada@example.com" in header.text_content()


@pytest.mark.django_db
def test_the_learner_overview_details_card_lists_name_email_status_date_added_and_last_active(
    staff_client: Client,
) -> None:
    learner = LearnerFactory(organisation=OrganisationFactory())

    document = _learner_page(staff_client, learner, "overview")

    labels = [dt.text_content().strip() for dt in document.cssselect("dl dt")]
    assert labels == ["Name", "Email", "Status", "Date added", "Last active"]


@pytest.mark.django_db
def test_the_learner_overview_last_active_row_shows_the_date(
    staff_client: Client,
) -> None:
    learner = LearnerFactory(
        organisation=OrganisationFactory(),
        user=UserFactory(last_active=datetime(2026, 3, 4, 15, 30, tzinfo=UTC)),
    )

    document = _learner_page(staff_client, learner, "overview")

    (value,) = document.xpath(
        "//dt[normalize-space()='Last active']/following-sibling::dd[1]"
    )
    assert value.text_content().strip() == "4 Mar 2026"


@pytest.mark.django_db
def test_the_learner_overview_last_active_row_reads_never_without_activity(
    staff_client: Client,
) -> None:
    learner = LearnerFactory(
        organisation=OrganisationFactory(), user=UserFactory(last_active=None)
    )

    document = _learner_page(staff_client, learner, "overview")

    (value,) = document.xpath(
        "//dt[normalize-space()='Last active']/following-sibling::dd[1]"
    )
    assert value.text_content().strip() == "Never"
