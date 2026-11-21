"""The educator interface's section configs and the pages they render."""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

import lxml.html
import pytest
import time_machine

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.comms.factories import (
    MessageFactory,
    NotificationFactory,
)
from freedom_ls.comms.messaging import encode_cursor
from freedom_ls.comms.models import Message
from freedom_ls.content_engine.factories import (
    CourseFactory,
)
from freedom_ls.educator_interface import views as educator_views
from freedom_ls.educator_interface.events import COHORT_CHANGED, LEARNER_CHANGED
from freedom_ls.educator_interface.learner_import import (
    PREVIEW_LABEL_TONES,
    create_learner_import,
    run_learner_import,
)
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    OrganisationAuditLogTable,
)
from freedom_ls.educator_interface.panels.cohort.data_tables import (
    CohortDataTable,
    LearnerCohortDataTable,
)
from freedom_ls.educator_interface.panels.course.data_tables import (
    CourseCohortRegistrationDataTable,
    CourseDataTable,
    CourseLearnerRegistrationDataTable,
)
from freedom_ls.educator_interface.panels.learner.bulk_actions import (
    DeactivateLearnersBulkAction,
)
from freedom_ls.educator_interface.panels.learner.data_table_panels import (
    LearnerHistoryPanel,
)
from freedom_ls.educator_interface.panels.learner.data_tables import (
    CohortLearnerDataTable,
    LearnerDataTable,
)
from freedom_ls.educator_interface.panels.staff.data_tables import StaffDataTable
from freedom_ls.educator_interface.tests.helpers import (
    _add_member,
    _audit_log_rows,
    _audit_log_url,
    _card_summary,
    _export_audit_csv,
    _get_document,
    _grant,
    _header_of,
    _history_entry,
    _history_export_url,
    _history_rows,
    _interface_url,
    _learner_page,
    _msg_conversation,
    _msg_educator,
    _msg_learner,
    _msg_url,
    _notes_for,
    _older_url,
    _open_conversation,
    _oversight_scene,
    _region_text,
    _shared_and_own_course_world,
    _shared_by_notes_by_row,
    _viewed_entries,
    get_interface_page,
    messages_section,
    organisation_admin_viewer,
    page_after_adding_rows,
    profile_picture_sources,
)
from freedom_ls.educator_interface.tests.interface_walk import (
    WalkedPanel,
    walk_interface,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import (
    add_to_cohort,
    move_between_cohorts,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    ImportLabel,
    ImportStatus,
    Learner,
    LearnerImport,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTMEMBERSHIP,
    ADD_LEARNER,
    VIEW_COHORT,
    VIEW_LEARNER,
    VIEW_ORGANISATION,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.learner_management.utils import register_cohort_for_course
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.bulk_runs import run_bulk_action
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.site_context import drop_ambient_request

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper

    from django.test.client import _MonkeyPatchedWSGIResponse


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
    assert "Course completion" not in region.text_content()


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


# A cohort page holds two tables, its course registrations on the Courses
# tab and its learners on the Learners tab. Each paginates through its own
# table key, so a learners page in the address bar leaves the course
# registrations on their own page.


def _cohort_url(cohort: Cohort) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cohort.organisation.slug,
            "path_string": f"cohorts/{cohort.pk}",
        },
    )


@pytest.mark.django_db
def test_learners_page_param_leaves_course_registrations_on_page_one(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Big Cohort")
    for i in range(DataTable.get_page_size() + 1):
        learner = LearnerFactory(
            user=UserFactory(first_name=f"Learner{i:02d}", last_name="Test"),
            organisation=organisation,
        )
        CohortMembershipFactory(cohort=cohort, learner=learner)
    for i in range(2):
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title=f"Course {i}")
        )
    client = logged_in_client(UserFactory(superuser=True))

    learners_tab = client.get(
        f"{_cohort_url(cohort)}/__tabs/learners", {"learners-page": "2"}
    )
    courses_tab = client.get(
        f"{_cohort_url(cohort)}/__tabs/courses", {"learners-page": "2"}
    )

    assert learners_tab.status_code == 200
    content = learners_tab.content.decode()
    # The learners table is on its own page 2: the last learner shows, the
    # 1st (on page 1) does not.
    assert f"Learner{DataTable.get_page_size():02d}" in content
    assert "Learner00" not in content
    # The course registrations table is untouched, still on page 1.
    assert courses_tab.status_code == 200
    content = courses_tab.content.decode()
    assert "Course 0" in content
    assert "Course 1" in content


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
def test_settings_offers_deactivate_on_an_active_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    page_url = _interface_url(organisation.slug, f"cohorts/{cohort.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/settings")

    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/deactivate" in triggers
    )
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/reactivate"
        not in triggers
    )


@pytest.mark.django_db
def test_settings_offers_reactivate_on_an_inactive_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, is_active=False)
    page_url = _interface_url(organisation.slug, f"cohorts/{cohort.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/settings")

    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/reactivate" in triggers
    )
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/deactivate"
        not in triggers
    )


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


def _cohort_page(client: Client, cohort: Cohort) -> lxml.html.HtmlElement:
    return _get_document(
        client, _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}")
    )


def _add_cohort_progress(
    registration: CohortCourseRegistration, learner: Learner, completed: bool
) -> None:
    CourseProgressFactory(
        learner=learner,
        course=registration.course,
        learner_registration=None,
        cohort_registration=registration,
        completed_time=timezone.now() if completed else None,
    )


def _completion_card(document: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (card,) = document.cssselect("section[data-panel='completion']")
    return card


@pytest.fixture
def completion_scenario() -> tuple[Cohort, CohortCourseRegistration, Learner]:
    """A cohort registered for one course, with two members holding one course
    progress record each; the returned learner's record is the completed one."""
    cohort = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))
    registration = cast(
        CohortCourseRegistration,
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title="Algebra")
        ),
    )
    done = _add_member(cohort)
    _add_cohort_progress(registration, done, completed=True)
    _add_cohort_progress(registration, _add_member(cohort), completed=False)
    return cohort, registration, done


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
def test_the_courses_tab_lists_the_course_registrations(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    (region,) = document.cssselect("[data-tab-set]")
    assert "Algebra" in region.text_content()


@pytest.mark.django_db
def test_course_completion_reads_one_of_two_completed(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
):
    cohort, _, _ = completion_scenario

    card = _completion_card(_cohort_page(staff_client, cohort))

    text = " ".join(card.text_content().split())
    assert "Algebra" in text
    assert "1 of 2 completed" in text


@pytest.mark.django_db
def test_the_course_completion_list_shows_no_list_markers(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
):
    """The theme bullets and indents bare lists, so the card's rows had both."""
    cohort, _, _ = completion_scenario

    card = _completion_card(_cohort_page(staff_client, cohort))

    (course_list,) = card.cssselect("ul")
    assert "list-none" in course_list.get("class").split()


@pytest.mark.django_db
def test_course_completion_progress_bar_is_at_fifty(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
):
    cohort, _, _ = completion_scenario

    card = _completion_card(_cohort_page(staff_client, cohort))

    (bar,) = card.cssselect("progress")
    assert bar.get("value") == "50"


@pytest.mark.django_db
def test_course_completion_falls_when_the_completed_member_leaves(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
):
    cohort, _, done = completion_scenario
    CohortMembership.objects.get(cohort=cohort, learner=done).delete()

    card = _completion_card(_cohort_page(staff_client, cohort))

    assert "0 of 1 completed" in " ".join(card.text_content().split())


@pytest.mark.django_db
def test_an_inactive_cohort_still_shows_completion_for_active_registrations(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
):
    cohort, _, _ = completion_scenario
    cohort.is_active = False
    cohort.save()

    card = _completion_card(_cohort_page(staff_client, cohort))

    assert "1 of 2 completed" in " ".join(card.text_content().split())


@pytest.mark.django_db
def test_course_completion_leaves_out_an_inactive_registration(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Retired"), is_active=False
    )

    card = _completion_card(_cohort_page(staff_client, cohort))

    assert "Retired" not in card.text_content()
    assert "No courses registered." in card.text_content()


@pytest.mark.django_db
def test_needs_attention_card_renders_a_skeleton_that_fetches_its_body(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    (card,) = document.cssselect("section[data-panel='attention']")
    (region,) = card.cssselect("div[aria-busy='true']")
    (fetch,) = region.cssselect("[hx-trigger='load']")
    assert fetch.get("hx-get").endswith("/__panels/attention?loaded=1")


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


def _settings_url(organisation: Organisation, cohort: Cohort) -> str:
    return _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/settings")


def _staff_section(document):
    (section,) = document.cssselect("section[data-panel='staff']")
    return section


@pytest.mark.django_db
def test_the_settings_tab_names_each_staff_member_and_their_role(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(
        user__first_name="Ada", user__last_name="Lovelace", organisation=organisation
    ).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, admin, "organisation_admin", organisation)

    document = _get_document(
        logged_in_client(admin), _settings_url(organisation, cohort)
    )

    text = " ".join(_staff_section(document).text_content().split())
    assert "Ada Lovelace" in text
    assert "Cohort Admin" in text or "Cohort admin" in text
    assert not document.cssselect("section[data-panel='educators']")


@pytest.mark.django_db
def test_the_settings_tab_staff_names_are_small_semibold_beside_a_small_avatar(
    mock_site_context, logged_in_client
):
    """A staff member is the small person row. The name used to render at the
    base size and regular weight beside a medium avatar."""
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(
        user__first_name="Ada", user__last_name="Lovelace", organisation=organisation
    ).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, admin, "organisation_admin", organisation)

    document = _get_document(
        logged_in_client(admin), _settings_url(organisation, cohort)
    )

    (name,) = [
        n
        for n in _staff_section(document).cssselect("span.truncate")
        if n.text_content().strip() == "Ada Lovelace"
    ]
    classes = " ".join(
        " ".join(
            a.get("class", "")
            for a in [name, *name.iterancestors("span", "div")]
            if a.getparent() is not None and a.tag != "li"
        ).split()
    )
    assert "text-sm" in classes
    assert "font-semibold" in classes
    assert _staff_section(document).cssselect("span.size-6")
    assert not _staff_section(document).cssselect("span.size-8")


@pytest.mark.django_db
def test_the_settings_tab_shows_a_nameless_staff_members_email_as_stored(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(
        user__first_name="",
        user__last_name="",
        user__email="Mixed.Case@Example.com",
        organisation=organisation,
    ).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, admin, "organisation_admin", organisation)

    document = _get_document(
        logged_in_client(admin), _settings_url(organisation, cohort)
    )

    assert "Mixed.Case@Example.com" in _staff_section(document).text_content()


@pytest.mark.django_db
def test_the_settings_tab_lists_a_person_added_from_the_cohort_page(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(
        LearnerFactory(user__superuser=True).user,
        admin,
        "organisation_admin",
        organisation,
    )
    ada = UserFactory(first_name="Ada", last_name="Lovelace", email="ada@example.com")
    client = logged_in_client(admin)

    client.post(
        _settings_url(organisation, cohort)
        + "/__panels/staff/__actions/add_staff_member",
        {
            "step": "submit",
            "email": "ada@example.com",
            "role": "cohort_viewer",
            "cohorts": [str(cohort.pk)],
            "confirmed": "1",
        },
        HTTP_HX_REQUEST="true",
    )

    document = _get_document(client, _settings_url(organisation, cohort))
    assert ada.display_name in _staff_section(document).text_content()


@pytest.mark.django_db
def test_the_settings_tab_offers_add_staff_member_beside_its_staff_heading(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    LearnerFactory(organisation=organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(staff_client, _settings_url(organisation, cohort))

    section = _staff_section(document)
    assert "No staff assigned to this cohort." in section.text_content()
    (trigger,) = section.cssselect("button[hx-get]")
    assert trigger.get("hx-get") == (
        _settings_url(organisation, cohort)
        + "/__panels/staff/__actions/add_staff_member"
    )
    assert "btn-sm" in trigger.get("class").split()
    footer_urls = {
        b.get("hx-get")
        for b in document.cssselect("section[data-panel] footer button")
        if b.get("hx-get")
    }
    assert not any(url.endswith("/__actions/add_staff_member") for url in footer_urls)


def _staff_on(
    organisation: Organisation, cohort: Cohort, role: str = "cohort_admin"
) -> User:
    holder = cast(
        User, LearnerFactory(user__staff=True, organisation=organisation).user
    )
    assign_role(LearnerFactory(user__superuser=True).user, holder, role, cohort)
    return holder


def _staff_triggers(section) -> list[str]:
    return [button.get("hx-get") for button in section.cssselect("button[hx-get]")]


def _register_triggers(document: lxml.html.HtmlElement, cohort: Cohort) -> list[str]:
    url = _interface_url(
        cohort.organisation.slug,
        f"cohorts/{cohort.pk}/__tabs/courses/__actions/register",
    )
    return [
        button.get("hx-get")
        for button in document.cssselect("button[hx-get]")
        if button.get("hx-get") == url
    ]


@pytest.mark.django_db
def test_a_cohort_admin_sees_the_staff_section_alone_on_the_settings_tab(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    me = _staff_on(organisation, cohort)
    _staff_on(organisation, cohort, "cohort_viewer")

    document = _get_document(logged_in_client(me), _settings_url(organisation, cohort))

    page = _settings_url(organisation, cohort)
    assert f"{page}/__panels/staff/__actions/add_staff_member" in _staff_triggers(
        _staff_section(document)
    )
    assert not document.cssselect("form[hx-post$='/__actions/edit']")
    assert "Deactivating stops" not in document.text_content()
    assert not document.cssselect("section[data-panel='status']")
    assert not document.cssselect("section[data-panel='name']")


@pytest.mark.django_db
def test_each_cohort_role_row_offers_change_role_and_remove_from_cohort_the_viewers_own_included(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    me = _staff_on(organisation, cohort)
    colleague = _staff_on(organisation, cohort, "cohort_viewer")

    document = _get_document(logged_in_client(me), _settings_url(organisation, cohort))

    actions = f"{_settings_url(organisation, cohort)}/__panels/staff/__actions"
    assert set(_staff_triggers(_staff_section(document))) == {
        f"{actions}/change_role?user={colleague.pk}&role=cohort_viewer",
        f"{actions}/remove_staff_from_cohort?user={colleague.pk}&role=cohort_viewer",
        f"{actions}/change_role?user={me.pk}&role=cohort_admin",
        f"{actions}/remove_staff_from_cohort?user={me.pk}&role=cohort_admin",
        f"{actions}/add_staff_member",
    }


@pytest.mark.django_db
def test_an_organisation_role_row_shows_only_its_role_to_a_viewer_who_can_open_staff(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(
        LearnerFactory(user__superuser=True).user,
        admin,
        "organisation_admin",
        organisation,
    )
    other = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(
        LearnerFactory(user__superuser=True).user,
        other,
        "organisation_admin",
        organisation,
    )

    document = _get_document(
        logged_in_client(admin), _settings_url(organisation, cohort)
    )

    section = _staff_section(document)
    (row,) = [
        li for li in section.cssselect("li") if other.display_name in li.text_content()
    ]
    assert "Organisation admin" in row.text_content()
    assert "whole organisation" not in row.text_content().lower()
    assert "Change it in Staff" not in row.text_content()
    assert not row.cssselect("button")
    assert not row.cssselect("a[href$='/staff']")


@pytest.mark.django_db
def test_an_organisation_role_row_shows_only_its_role_to_a_cohort_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(
        LearnerFactory(user__superuser=True).user,
        admin,
        "organisation_admin",
        organisation,
    )
    me = _staff_on(organisation, cohort)

    document = _get_document(logged_in_client(me), _settings_url(organisation, cohort))

    section = _staff_section(document)
    assert "Organisation admin" in section.text_content()
    assert "Set for the whole organisation." not in section.text_content()
    assert not section.cssselect("a[href$='/staff']")


@pytest.mark.django_db
def test_the_courses_tab_shows_each_registrations_status_badge(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra"), is_active=True
    )
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Geometry"), is_active=False
    )

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    (region,) = document.cssselect("[data-tab-set]")
    text = " ".join(region.text_content().split())
    assert "Active" in text
    assert "Inactive" in text


@pytest.mark.django_db
def test_the_courses_tab_offers_register_to_a_cohort_admin(
    mock_site_context, logged_in_client
):
    cohort = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=cohort.organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    document = _get_document(
        logged_in_client(educator),
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    (trigger,) = [
        button
        for button in document.cssselect("button[hx-get]")
        if button.get("hx-get", "").endswith("/__actions/register")
    ]
    assert " ".join(trigger.text_content().split()) == "Register for a course"
    assert len(_register_triggers(document, cohort)) == 1


@pytest.mark.django_db
def test_the_courses_tab_shows_a_cohort_viewer_no_register_trigger(
    mock_site_context, logged_in_client
):
    cohort = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=cohort.organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)

    document = _get_document(
        logged_in_client(viewer),
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    assert _register_triggers(document, cohort) == []


@pytest.mark.django_db
def test_an_inactive_cohorts_courses_tab_shows_no_register_trigger(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    assert _register_triggers(document, cohort) == []


def _deactivate_triggers(document: lxml.html.HtmlElement, cohort: Cohort) -> list[str]:
    prefix = _interface_url(
        cohort.organisation.slug,
        f"cohorts/{cohort.pk}/__tabs/courses/__actions/deactivate_cohort_registration",
    )
    return [
        button.get("hx-get")
        for button in document.cssselect("button[hx-get]")
        if button.get("hx-get").startswith(prefix)
    ]


@pytest.mark.django_db
def test_the_courses_tab_offers_deactivate_only_on_active_registrations(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())
    active = CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra"), is_active=True
    )
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Geometry"), is_active=False
    )

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    # The table and its small-screen card list each render the trigger.
    (trigger,) = set(_deactivate_triggers(document, cohort))
    assert trigger.endswith(f"?registration={active.pk}")


@pytest.mark.django_db
def test_an_inactive_cohorts_courses_tab_shows_no_deactivate_trigger(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)
    CohortCourseRegistrationFactory(cohort=cohort, is_active=True)

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    assert _deactivate_triggers(document, cohort) == []


@pytest.mark.django_db
def test_a_cohort_viewers_courses_tab_renders_no_action_buttons(
    mock_site_context, logged_in_client
):
    cohort = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))
    CohortCourseRegistrationFactory(cohort=cohort, is_active=True)
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=cohort.organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)

    document = _get_document(
        logged_in_client(viewer),
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    (region,) = document.cssselect("[data-tab-set]")
    assert region.cssselect("button[hx-get]") == []


def _cohort_history_access(
    client: Client, organisation: Organisation, cohort: Cohort
) -> tuple[bool, int]:
    """Whether the cohort page lists a History tab, and the status of the
    tab's own URL."""
    page = client.get(_interface_url(organisation.slug, f"cohorts/{cohort.pk}"))
    hrefs = []
    if page.status_code == 200:
        document = lxml.html.fromstring(page.content.decode())
        (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
        hrefs = [a.get("href").rsplit("/", 1)[-1] for a in nav.cssselect("a")]
    response = client.get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )
    return "history" in hrefs, response.status_code


@pytest.mark.django_db
def test_a_cohort_admin_reads_the_history_of_a_cohort_they_administer(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    colleague = UserFactory()
    assign_role(grantor, colleague, "cohort_viewer", cohort)
    client = logged_in_client(educator)

    shown = _cohort_history_access(client, organisation, cohort)
    history = client.get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )

    assert shown == (True, 200)
    assert "Role assigned" in history.content.decode()


@pytest.mark.django_db
def test_a_cohort_admin_gets_no_history_on_a_cohort_they_do_not_administer(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    own = cast(Cohort, CohortFactory(organisation=organisation))
    other = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", own)
    assign_role(grantor, educator, "cohort_viewer", other)

    assert _cohort_history_access(logged_in_client(educator), organisation, other) == (
        False,
        404,
    )


@pytest.mark.django_db
def test_a_cohort_admin_gets_no_organisation_audit_log(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = logged_in_client(educator).get(
        _interface_url(organisation.slug, "audit-log")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_export_entry_shows_on_the_audit_log_and_not_on_the_learner_history(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Able"
    )
    _history_entry(learner)
    _export_audit_csv(staff_client, _history_export_url(learner))

    audit_rows = _audit_log_rows(
        _get_document(staff_client, _audit_log_url(organisation))
    )
    history_rows = _history_rows(_learner_page(staff_client, learner, "history"))

    exported = [row for row in audit_rows if "Audit log exported" in row[2]]
    assert (
        len(exported),
        "Ada Able: 1 entry" in exported[0][2],
        len(history_rows),
    ) == (
        1,
        True,
        1,
    )


@pytest.mark.django_db
def test_an_active_cohorts_learners_tab_offers_remove_for_each_member(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())
    member = _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    triggers = {
        button.get("hx-get")
        for button in document.cssselect("button[hx-get]")
        if "remove_from_cohort" in button.get("hx-get")
    }
    assert {t.split("?learner=")[1] for t in triggers} == {str(member.pk)}


@pytest.mark.django_db
def test_a_learner_rows_remove_trigger_uses_the_error_variant(staff_client: Client):
    """The per-row Remove trigger is styled as a destructive action, not secondary."""
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    buttons = [
        b
        for b in document.cssselect("button[hx-get]")
        if "remove_from_cohort?learner=" in b.get("hx-get")
    ]
    assert buttons
    assert all("btn-error" in b.get("class") for b in buttons)


@pytest.mark.django_db
def test_a_learner_rows_remove_and_move_triggers_name_the_learner(
    staff_client: Client,
):
    """Ten rows of bare 'Remove' and 'Move' are indistinguishable to a screen reader."""
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Cohort Alpha")
    learner = _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    labels = {
        button.get("aria-label")
        for button in document.cssselect("button[hx-get]")
        if f"?learner={learner.pk}" in button.get("hx-get")
    }
    assert labels == {
        f"Remove {learner.user.display_name} from Cohort Alpha",
        f"Move {learner.user.display_name} to another cohort",
    }


@pytest.mark.django_db
def test_a_registration_rows_deactivate_trigger_names_the_course(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra"), is_active=True
    )

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    labels = {
        button.get("aria-label")
        for button in document.cssselect("button[hx-get]")
        if "deactivate_cohort_registration?registration=" in button.get("hx-get")
    }
    assert labels == {"Deactivate the Algebra registration"}


def _export_csv(client: Client, path_string: str, organisation: Organisation):
    """The learners table's CSV export for ``path_string``: (header, rows, filename)."""
    response = client.get(
        _interface_url(organisation.slug, path_string), {"learners-export": "csv"}
    )
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    header, *rows = list(csv.reader(io.StringIO(body, newline="")))
    return header, rows, response["Content-Disposition"]


@pytest.mark.django_db
def test_a_cohorts_learners_tab_exports_its_members_as_a_csv_named_for_the_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Night class")
    course = CourseFactory(title="Hydrology")
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    member = CohortMembershipFactory(
        cohort=cohort,
        learner__organisation=organisation,
        learner__user=UserFactory(
            first_name="Ada", last_name="Able", email="ada@example.com"
        ),
    ).learner
    course_progress_record(course, member.user, last_accessed_time=timezone.now())
    CohortMembershipFactory(
        cohort=CohortFactory(organisation=organisation, name="Day class"),
        learner__organisation=organisation,
        learner__user=UserFactory(first_name="Bo", last_name="Baker"),
    )

    header, rows, disposition = _export_csv(
        staff_client, f"cohorts/{cohort.pk}/__tabs/learners", organisation
    )

    assert header == ["Name", "Email", "Status", "Cohorts", "Courses", "Last active"]
    assert [row[:5] for row in rows] == [
        ["Ada Able", "ada@example.com", "Active", "Night class", "Hydrology"]
    ]
    assert rows[0][5] == timezone.localdate().strftime("%Y-%m-%d")
    assert disposition == (
        f'attachment; filename="learners-night-class-{timezone.localdate():%Y-%m-%d}.csv"'
    )


@pytest.mark.django_db
def test_the_learners_export_neutralises_a_formula_looking_name_and_leaves_never_active_blank(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    CohortMembershipFactory(
        cohort=CohortFactory(organisation=organisation),
        learner__organisation=organisation,
        learner__user=UserFactory(
            first_name='=HYPERLINK("http://evil","x")', last_name=""
        ),
    )

    _header, rows, _disposition = _export_csv(staff_client, "learners", organisation)

    (row,) = rows
    assert row[0].startswith("'=HYPERLINK")
    assert row[5] == ""


@pytest.mark.django_db
def test_the_learners_export_stays_scoped_when_the_site_thread_local_is_cleared(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    for name in ("Ada", "Bo"):
        CohortMembershipFactory(
            cohort=CohortFactory(organisation=organisation),
            learner__organisation=organisation,
            learner__user=UserFactory(first_name=name, last_name="Learner"),
        )

    response = staff_client.get(
        _interface_url(organisation.slug, "learners"), {"learners-export": "csv"}
    )
    drop_ambient_request()
    body = b"".join(response.streaming_content).decode("utf-8-sig")

    _header, *rows = list(csv.reader(io.StringIO(body, newline="")))
    assert sorted(row[0] for row in rows) == ["Ada Learner", "Bo Learner"]


@pytest.mark.django_db
def test_the_learners_tab_toolbar_offers_the_csv_export(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    links = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert links
    assert all("learners-export=csv" in a.get("href") for a in links)


@pytest.mark.django_db
def test_an_inactive_cohorts_learners_tab_renders_no_remove_control(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)
    _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    assert "remove_from_cohort" not in lxml.html.tostring(document).decode()


@pytest.mark.django_db
def test_a_members_page_renders_an_inactive_cohorts_row_without_any_action(
    staff_client: Client,
):
    cohort = CohortFactory(
        organisation=OrganisationFactory(), is_active=False, name="Dormant group"
    )
    learner = _add_member(cohort)

    document = _learner_page(staff_client, learner)

    (row,) = document.xpath("//tr[contains(., 'Dormant group')]")
    assert row.cssselect("button") == []


@pytest.mark.django_db
def test_an_inactive_cohorts_learners_tab_renders_no_add_learners_control(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    assert "add_existing_learners" not in lxml.html.tostring(document).decode()


@pytest.mark.django_db
def test_the_add_to_cohort_picker_on_a_learners_page_offers_no_inactive_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    inactive = CohortFactory(organisation=organisation, is_active=False)
    learner = LearnerFactory(organisation=organisation)

    response = staff_client.get(
        _interface_url(
            organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
        ),
        HTTP_HX_REQUEST="true",
    )

    assert str(inactive.pk) not in response.content.decode()


@pytest.mark.django_db
def test_the_add_to_cohort_picker_offers_no_inactive_cohort_after_a_submit_with_no_choice(
    staff_client: Client,
):
    """A submit with no cohort chosen used to re-render the select with the
    organisation's inactive cohorts, which the first render never offered."""
    organisation = OrganisationFactory()
    inactive = CohortFactory(organisation=organisation, is_active=False)
    learner = LearnerFactory(organisation=organisation)

    response = staff_client.post(
        _interface_url(
            organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
        ),
        {"cohort": ""},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert str(inactive.pk) not in response.content.decode()


@pytest.mark.django_db
def test_an_inactive_cohorts_learners_tab_renders_no_move_control(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)
    _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    assert "__actions/move" not in lxml.html.tostring(document).decode()


@pytest.mark.django_db
def test_a_members_page_renders_an_inactive_cohorts_row_with_no_move(
    staff_client: Client,
):
    cohort = CohortFactory(
        organisation=OrganisationFactory(), is_active=False, name="Dormant group"
    )
    learner = _add_member(cohort)

    document = _learner_page(staff_client, learner)

    (row,) = document.xpath("//tr[contains(., 'Dormant group')]")
    assert "__actions/move" not in lxml.html.tostring(row).decode()


@pytest.mark.django_db
def test_an_active_cohorts_learners_tab_offers_move_for_each_member(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())
    member = _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    triggers = {
        button.get("hx-get")
        for button in document.cssselect("button[hx-get]")
        if "__actions/move" in button.get("hx-get")
    }
    assert {t.split("?learner=")[1] for t in triggers} == {str(member.pk)}


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


@pytest.mark.django_db
def test_the_cohort_settings_panel_refreshes_on_member_changes(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(staff_client, _settings_url(organisation, cohort))

    (card,) = document.cssselect("section[data-panel='staff']")
    assert "staffChanged from:body" in card.get("hx-trigger")


@pytest.mark.django_db
def test_the_cohort_history_panel_refreshes_on_member_changes(staff_client: Client):
    """Adding a staff member from the Settings tab writes a role.assigned
    entry with the cohort as subject and answers with staffChanged alone."""
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(
        staff_client,
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history"),
    )

    (card,) = document.cssselect("section[data-panel='history']")
    assert "staffChanged from:body" in card.get("hx-trigger")


def _cohort_history_tab(client: Client, cohort: Cohort) -> lxml.html.HtmlElement:
    return _get_document(
        client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history"),
    )


@pytest.mark.django_db
def test_a_move_shows_on_both_cohorts_and_the_learner_history_tabs(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    source = CohortFactory(organisation=organisation, name="Alpha")
    destination = CohortFactory(organisation=organisation, name="Beta")
    CohortMembershipFactory(learner=learner, cohort=source)
    move_between_cohorts(learner, source, destination, actor=UserFactory())

    shown = [
        _history_rows(_cohort_history_tab(staff_client, source)),
        _history_rows(_cohort_history_tab(staff_client, destination)),
        _history_rows(_learner_page(staff_client, learner, "history")),
    ]

    assert [[row[2] for row in rows] for rows in shown] == [
        ["Learner moved between cohorts From Alpha to Beta"]
    ] * 3


@pytest.mark.django_db
def test_an_add_shows_on_the_cohort_history_tab_and_not_on_another_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, name="Alpha")
    other = CohortFactory(organisation=organisation, name="Beta")
    add_to_cohort(learner, cohort, actor=UserFactory())

    rows = _history_rows(_cohort_history_tab(staff_client, cohort))
    other_page = _cohort_history_tab(staff_client, other)

    assert (
        ["Alpha" in row[2] for row in rows],
        "Alpha" in _region_text(other_page),
    ) == (
        [True],
        False,
    )


@pytest.mark.django_db
def test_the_cohort_history_tab_renders_its_empty_state(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())

    response = staff_client.get(
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )

    template_names = [t.name for t in response.templates]
    assert "panel_framework/partials/table_empty.html" in template_names


@pytest.mark.django_db
def test_a_cohort_viewer_gets_no_cohort_history_tab_and_a_404_on_its_url(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)
    client = logged_in_client(viewer)

    document = _cohort_page(client, cohort)
    response = client.get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )

    hrefs = [a.get("href").rsplit("/", 1)[-1] for a in document.cssselect("nav a")]
    assert ("history" in hrefs, response.status_code) == (False, 404)


@pytest.mark.django_db
def test_a_cohort_registration_shows_on_the_cohort_history_tab(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    register_cohort_for_course(cohort, CourseFactory(title="Algebra"))

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history"),
    )

    rows = _history_rows(document)
    assert [row[2] for row in rows] == ["Cohort registered for course Algebra"]


@pytest.mark.django_db
def test_the_cohort_history_tab_names_who_each_row_is_about(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Alpha")
    actor = UserFactory()
    for first_name in ["Ben", "Pat"]:
        learner = LearnerFactory(
            organisation=organisation,
            user=UserFactory(first_name=first_name, last_name="Learner"),
        )
        add_to_cohort(learner, cohort, actor=actor)

    document = _cohort_history_tab(staff_client, cohort)

    headers = [
        th.text_content().strip()
        for th in document.cssselect("[data-tab-set] thead th")
    ]
    rows = _history_rows(document)
    assert (headers, sorted(row[3].split(maxsplit=1)[1] for row in rows)) == (
        ["Details", "When", "Who", "What", "Target"],
        ["Ben Learner", "Pat Learner"],
    )


@pytest.mark.django_db
def test_the_cohort_history_card_names_who_the_row_is_about(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=cohort,
        organisation=cohort.organisation,
        target_label="<b>bold</b>",
    )

    html = staff_client.get(
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    ).content.decode()

    assert html.count("&lt;b&gt;bold&lt;/b&gt;") >= 2


@pytest.mark.django_db
def test_the_cohort_history_card_shows_the_label_then_labelled_when_who_and_target(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=cohort,
        organisation=cohort.organisation,
        action="learner.deactivated",
        actor_label="Ada Admin",
        target_label="Alpha",
        reason="Asked to leave",
    )

    document = _cohort_history_tab(staff_client, cohort)

    (card,) = document.cssselect("[data-tab-set] ul > li")
    assert _card_summary(card) == (
        "Learner deactivated",
        ["When", "Who", "Target"],
        ["Ada Admin", "Alpha"],
        True,
    )


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


@pytest.mark.django_db
@messages_section
class TestOversight:
    @pytest.fixture
    def scene(self):
        return _oversight_scene()

    @pytest.fixture
    def long_scene(self, scene, settings):
        settings.MESSAGE_PAGE_SIZE = 3
        _, educator, _, conversation = scene
        base = timezone.now() - timedelta(days=3)
        messages = []
        for i in range(7):
            message = MessageFactory(
                conversation=conversation, sender=educator, body=f"m{i}"
            )
            Message.objects.filter(pk=message.pk).update(
                created_at=base + timedelta(minutes=i)
            )
            messages.append(Message.objects.get(pk=message.pk))
        return scene, messages

    def test_the_modal_control_points_at_the_oversight_endpoint(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, conversation), _ = long_scene

        response = _open_conversation(
            msg_client_for(_msg_educator(organisation)), learner, conversation.pk
        )

        page = lxml.html.fromstring(response.content.decode())
        (button,) = page.xpath("//div[@id='read-only-thread-older']//button")
        assert button.get("hx-get").startswith(_older_url(learner, conversation.pk, ""))

    def test_the_modal_thread_ids_differ_from_the_own_threads(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, conversation), _ = long_scene

        response = _open_conversation(
            msg_client_for(_msg_educator(organisation)), learner, conversation.pk
        )

        page = lxml.html.fromstring(response.content.decode())
        assert page.xpath("//ol[@id='read-only-thread-log']")
        assert not page.xpath("//*[@id='thread-log' or @id='thread-older']")
        (button,) = page.xpath("//div[@id='read-only-thread-older']//button")
        assert button.get("hx-target") == "#read-only-thread-log"

    def test_the_older_endpoint_pages_back_and_writes_no_entry(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, conversation), messages = long_scene
        client = msg_client_for(_msg_educator(organisation))

        response = client.get(
            _older_url(learner, conversation.pk, encode_cursor(messages[4])),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        tree = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
        ids = [li.get("id") for li in tree.xpath("./li[not(@hx-swap-oob)]")]
        assert ids == [f"msg-{m.pk}" for m in messages[1:4]]
        button = tree.xpath("./div[@id='read-only-thread-older']//button")[0]
        assert button.get("hx-get").startswith(_older_url(learner, conversation.pk, ""))
        assert button.get("hx-target") == "#read-only-thread-log"
        assert _viewed_entries() == []

    def test_the_older_endpoint_is_404_for_a_cohort_admin(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, conversation), messages = long_scene
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        cohort_admin = cast(User, UserFactory(staff=True))
        _grant(cohort_admin, "cohort_admin", cohort)

        response = msg_client_for(cohort_admin).get(
            _older_url(learner, conversation.pk, encode_cursor(messages[4])),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    def test_the_older_endpoint_is_404_outside_the_oversight_set(
        self, msg_client_for, long_scene
    ):
        (organisation, _, learner, _), messages = long_scene
        client = msg_client_for(_msg_educator(organisation))
        peer = _msg_learner(organisation, first_name="Peer")
        peer_conversation = _msg_conversation(peer.user, learner.user)
        cursor = encode_cursor(messages[4])

        for target in (peer_conversation.pk, uuid4(), "-" * 36):
            response = client.get(
                _older_url(learner, target, cursor), HTTP_HX_REQUEST="true"
            )
            assert response.status_code == 404, target

    def test_the_older_endpoint_is_404_for_another_organisations_learner(
        self, msg_client_for, long_scene
    ):
        (organisation, _, _, conversation), messages = long_scene
        stranger = _msg_learner(OrganisationFactory())

        response = msg_client_for(_msg_educator(organisation)).get(
            _older_url(
                stranger, conversation.pk, encode_cursor(messages[4]), organisation
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    def test_the_older_endpoint_is_404_when_messaging_is_off(
        self, msg_client_for, long_scene, settings
    ):
        (organisation, _, learner, conversation), messages = long_scene
        client = msg_client_for(_msg_educator(organisation))
        settings.MESSAGING_ENABLED = False

        response = client.get(
            _older_url(learner, conversation.pk, encode_cursor(messages[4])),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    @pytest.mark.parametrize("cursor", ["", "junk"])
    def test_a_missing_or_malformed_cursor_is_a_400(
        self, msg_client_for, long_scene, cursor
    ):
        (organisation, _, learner, conversation), _ = long_scene

        response = msg_client_for(_msg_educator(organisation)).get(
            _older_url(learner, conversation.pk, cursor), HTTP_HX_REQUEST="true"
        )

        assert response.status_code == 400


# bulk run status, polled by the table a background run was started from.
# The route is the framework's; these cover its wiring into this interface
# (the organisation scope, the refresh event and the notification hooks).


def _run_for(user: User, organisation: Organisation, **fields: object):
    return BulkActionRun.objects.create(
        site=organisation.site,
        scope=organisation,
        requested_by=user,
        action_path=(
            f"{DeactivateLearnersBulkAction.__module__}."
            f"{DeactivateLearnersBulkAction.__name__}"
        ),
        table_key="learners",
        action_name="deactivate",
        keys=[str(LearnerFactory(organisation=organisation).pk) for _ in range(2)],
        **fields,
    )


def _run_status_url(organisation: Organisation, run: BulkActionRun) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation.slug,
            "path_string": f"learners/__runs/{run.pk}",
        },
    )


@pytest.fixture
def run_world(logged_in_client: Callable[[User], Client], mock_site_context: Site):
    organisation = OrganisationFactory()
    requester = cast(User, UserFactory(superuser=True))
    return SimpleNamespace(
        organisation=organisation,
        requester=requester,
        client=logged_in_client(requester),
        run=_run_for(requester, organisation),
    )


def _poll(world: SimpleNamespace) -> _MonkeyPatchedWSGIResponse:
    client: Client = world.client
    return client.get(
        _run_status_url(world.organisation, world.run), HTTP_HX_REQUEST="true"
    )


@pytest.mark.django_db
def test_an_unfinished_run_answers_204(run_world: SimpleNamespace):
    response = _poll(run_world)

    assert (response.status_code, response.content) == (204, b"")


@pytest.mark.django_db
def test_a_finished_run_answers_the_result_modal_and_refreshes_the_table(
    run_world: SimpleNamespace, mock_site_context: Site
):
    run_bulk_action(str(run_world.run.pk), mock_site_context.pk)

    response = _poll(run_world)

    document = lxml.html.fromstring(response.content.decode())
    assert response.status_code == 200
    assert "2 learners changed." in document.text_content()
    assert json.loads(response["HX-Trigger"]) == {LEARNER_CHANGED: {"ids": []}}


@pytest.mark.django_db
def test_a_finished_run_marks_its_notification_read(
    run_world: SimpleNamespace, mock_site_context: Site
):
    run_bulk_action(str(run_world.run.pk), mock_site_context.pk)
    notification = NotificationFactory(
        user=run_world.requester,
        category="bulk_action.finished",
        target=run_world.run,
        data={"summary": "Deactivate finished: 2 learners changed."},
    )

    _poll(run_world)

    notification.refresh_from_db()
    assert notification.read_at is not None


@pytest.mark.django_db
def test_an_unfinished_run_leaves_its_notification_unread(
    run_world: SimpleNamespace,
):
    notification = NotificationFactory(
        user=run_world.requester,
        category="bulk_action.finished",
        target=run_world.run,
        data={"summary": "s"},
    )

    _poll(run_world)

    notification.refresh_from_db()
    assert notification.read_at is None


@pytest.mark.django_db
def test_a_run_is_a_404_for_another_user_of_the_organisation(
    run_world: SimpleNamespace, logged_in_client
):
    other = cast(User, UserFactory(superuser=True))

    response = logged_in_client(other).get(
        _run_status_url(run_world.organisation, run_world.run)
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_run_is_a_404_through_another_organisations_slug(
    run_world: SimpleNamespace,
):
    elsewhere = OrganisationFactory()

    response = run_world.client.get(_run_status_url(elsewhere, run_world.run))

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_learners_bar_promotes_four_actions_and_lists_the_rest_with_the_destructive_one_last_under_more(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    LearnerFactory(organisation=organisation)

    document = _get_document(
        staff_client, _interface_url(organisation.slug, "learners")
    )

    def labels(selector: str) -> list[str]:
        return [
            " ".join(element.text_content().split())
            for element in document.cssselect(selector)
        ]

    assert labels("div[data-total-count] > div > fieldset > button[formaction]") == [
        "Add to cohort",
        "Deactivate",
        "Reactivate",
        "Register for a course",
    ]
    assert labels("fieldset > span [role='menu'] button[formaction]") == [
        "Deactivate a course registration",
        "Resend setup email",
        "Remove from cohort",
    ]


@pytest.mark.django_db
def test_the_cohorts_bar_promotes_all_four_actions_and_has_no_more_menu(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation)

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    def labels(selector: str) -> list[str]:
        return [
            " ".join(element.text_content().split())
            for element in document.cssselect(selector)
        ]

    assert labels("div[data-total-count] > div > fieldset > button[formaction]") == [
        "Register for a course",
        "Deactivate a course registration",
        "Deactivate",
        "Reactivate",
    ]
    assert labels("[role='menu'] button[formaction]") == []


# learner import pages


def _import_url(organisation: Organisation, name: str, learner_import=None) -> str:
    kwargs: dict[str, object] = {"organisation_slug": organisation.slug}
    if learner_import is not None:
        kwargs["import_id"] = learner_import.pk
    return reverse(f"educator_interface:{name}", kwargs=kwargs)


def _csv_upload(*lines: str) -> SimpleUploadedFile:
    body = "email,first_name,last_name,cohort\n" + "\n".join(lines)
    return SimpleUploadedFile("learners.csv", body.encode(), "text/csv")


def _import_for(user: User, organisation: Organisation, *lines: str) -> LearnerImport:
    return create_learner_import(user, organisation, None, _csv_upload(*lines))


@pytest.fixture
def import_world(logged_in_client: Callable[[User], Client], mock_site_context: Site):
    organisation = OrganisationFactory()
    grantor = cast(User, UserFactory(superuser=True))
    admin = cast(User, LearnerFactory(user__staff=True, organisation=organisation).user)
    assign_role(grantor, admin, "organisation_admin", organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    cohort_admin = cast(
        User, LearnerFactory(user__staff=True, organisation=organisation).user
    )
    assign_role(grantor, cohort_admin, "cohort_admin", cohort)
    return SimpleNamespace(
        organisation=organisation,
        admin=admin,
        client=logged_in_client(admin),
        cohort=cohort,
        cohort_admin_client=logged_in_client(cohort_admin),
        logged_in_client=logged_in_client,
    )


@pytest.mark.django_db
def test_the_upload_page_shows_the_headers_the_stepper_and_the_file_input(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    assert page.cssselect("input[type=file]")
    assert [code.text for code in page.cssselect("[data-format-table] code")] == [
        "email",
        "first_name",
        "last_name",
        "cohort",
    ]
    assert page.cssselect("ol li[aria-current='step']")
    assert "Step 1 of 3" in page.text_content()


@pytest.mark.django_db
def test_the_format_table_has_one_row_per_header_with_only_email_required(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    rows = [
        (row.cssselect("td")[0].text_content().strip(), row.cssselect("td")[1].text)
        for row in page.cssselect("[data-format-table] tbody tr")
    ]
    assert rows == [
        ("email", "Required"),
        ("first_name", "Optional"),
        ("last_name", "Optional"),
        ("cohort", "Optional"),
    ]


@pytest.mark.django_db
def test_the_upload_page_states_the_row_and_file_size_limits(
    import_world: SimpleNamespace, settings, monkeypatch: pytest.MonkeyPatch
):
    settings.LEARNER_IMPORT_MAX_ROWS = 1500
    monkeypatch.setattr(
        "freedom_ls.educator_interface.views.MAX_UPLOAD_BYTES", 2 * 1024 * 1024
    )

    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    text = page.text_content().replace("\xa0", " ")
    assert "Add up to 1,500 learners at once, 2.0 MB per file" in " ".join(text.split())


@pytest.mark.django_db
def test_the_cohort_upload_page_describes_the_cohort_column_as_ignored(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation, name="Accra Jan")

    page = _get_document(
        import_world.client, _cohort_import_url(import_world.organisation, cohort)
    )

    cohort_row = page.cssselect("[data-format-table] tbody tr")[3]
    assert "Ignored: everyone goes into Accra Jan." in " ".join(
        cohort_row.text_content().split()
    )


@pytest.mark.django_db
def test_an_import_page_offers_a_back_link_to_the_learners_list(
    import_world: SimpleNamespace,
):
    organisation = import_world.organisation

    page = _get_document(
        import_world.client, _import_url(organisation, "learner_import")
    )

    (back,) = page.cssselect("#breadcrumbs a")
    assert back.get("href") == _interface_url(organisation.slug, "learners")
    assert back.text_content().strip() == "Learners"


@pytest.mark.django_db
def test_the_stepper_numbers_each_step_in_its_own_label(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    steps = page.cssselect("nav[aria-label='Import steps'] [data-step-label]")
    assert [" ".join(step.text_content().split()) for step in steps] == [
        "1. Upload",
        "2. Preview",
        "3. Result",
    ]


@pytest.mark.django_db
def test_the_stepper_line_names_the_current_step_for_narrow_screens(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    (stepper,) = page.cssselect("nav[aria-label='Import steps']")
    assert "Step 2 of 3: Preview" in " ".join(stepper.text_content().split())


@pytest.mark.django_db
def test_an_organisation_admin_passes_the_import_gate_and_a_cohort_admin_gets_the_403_page(
    import_world: SimpleNamespace,
):
    url = _import_url(import_world.organisation, "learner_import")

    allowed = import_world.client.get(url)
    denied = import_world.cohort_admin_client.get(url)

    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert (
        "can't import learners here"
        in lxml.html.fromstring(denied.content.decode()).text_content()
    )


@pytest.mark.django_db
def test_a_bad_file_is_a_422_with_a_focused_alert_and_stores_nothing(
    import_world: SimpleNamespace,
):
    response = import_world.client.post(
        _import_url(import_world.organisation, "learner_import"),
        {"file": SimpleUploadedFile("learners.csv", b"name\nAda\n")},
    )

    page = lxml.html.fromstring(response.content.decode())
    (alert,) = page.cssselect("#main-content [role=alert]")
    assert response.status_code == 422
    assert alert.get("autofocus") is not None
    assert "Unknown column(s): name" in alert.text_content()
    assert not LearnerImport.objects.exists()


@pytest.mark.django_db
def test_the_file_input_only_offers_csv_files(import_world: SimpleNamespace):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    (file_input,) = page.cssselect("input[type=file]")
    assert file_input.get("accept") == ".csv,text/csv"


@pytest.mark.django_db
def test_the_file_input_is_described_by_the_limits_line(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    (file_input,) = page.cssselect("input[type=file]")
    (limits,) = page.cssselect(f"#{file_input.get('aria-describedby')}")
    assert "rows" in limits.text_content()


@pytest.mark.django_db
def test_a_bad_file_page_still_wraps_the_input_in_the_drop_zone(
    import_world: SimpleNamespace,
):
    response = import_world.client.post(
        _import_url(import_world.organisation, "learner_import"),
        {"file": SimpleUploadedFile("learners.csv", b"name\nAda\n")},
    )

    page = lxml.html.fromstring(response.content.decode())
    (file_input,) = page.cssselect("input[type=file]")
    assert page.cssselect(f"label[for={file_input.get('id')}][data-drop-zone]")


@pytest.mark.django_db
def test_a_good_file_redirects_with_a_303_to_its_preview(
    import_world: SimpleNamespace,
):
    response = import_world.client.post(
        _import_url(import_world.organisation, "learner_import"),
        {"file": _csv_upload("a@example.com,Ada,Lovelace,")},
    )

    learner_import = LearnerImport.objects.get()
    assert response.status_code == 303
    assert response["Location"] == _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )


@pytest.mark.django_db
def test_the_preview_counts_each_label_and_offers_to_add_the_rows_that_can_be_added(
    import_world: SimpleNamespace,
):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "a@example.com,,,",
        "b@example.com,,,",
        f"{existing.user.email},,,",
        "nonsense,,,",
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    text = " ".join(page.text_content().split())
    tile_labels = [
        link.get("aria-label") for link in page.cssselect("a[data-label-filter]")
    ]
    assert "New account: 2" in tile_labels
    assert "Already a member: 1" in tile_labels
    assert "Error: 1" in tile_labels
    assert "1 row with errors will not be added." in text
    assert "2 new accounts will get a setup email." in text
    assert [
        button.text_content().strip()
        for button in page.cssselect("#main-content button[type=submit]")
    ] == ["Add 2 learners"]
    assert len(page.cssselect("[data-import-rows] tbody tr")) == 3


@pytest.mark.django_db
def test_a_preview_with_nothing_to_add_has_no_confirm_button_and_says_why(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "nonsense,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert not page.cssselect("#main-content form button[type=submit]")
    assert "Nothing can be added" in page.text_content()


@pytest.mark.django_db
def test_a_preview_with_no_new_accounts_omits_the_setup_email_line(
    import_world: SimpleNamespace,
):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin, import_world.organisation, f"{existing.user.email},,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert "setup email" not in page.text_content()


@pytest.mark.django_db
def test_a_result_with_nothing_not_added_omits_the_not_added_line(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    text = " ".join(page.text_content().split())
    assert "Added 1 learner." in text
    assert "not added" not in text


@pytest.mark.django_db
def test_a_result_with_no_new_accounts_omits_the_setup_email_line(
    import_world: SimpleNamespace,
):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin, import_world.organisation, f"{existing.user.email},,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert "setup email" not in page.text_content()


@pytest.mark.django_db
def test_confirming_runs_the_import_and_the_result_page_reports_it(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "a@example.com,,,",
        "b@example.com,,,",
        "nonsense,,,",
    )

    confirmed = import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )
    result_url = _import_url(
        import_world.organisation, "learner_import_result", learner_import
    )
    page = _get_document(import_world.client, result_url)

    text = " ".join(page.text_content().split())
    assert (confirmed.status_code, confirmed["Location"]) == (303, result_url)
    assert "Added 2 learners. 1 row was not added." in text
    assert "2 setup emails were sent." in text
    assert "Step 3 of 3" in text


@pytest.mark.django_db
def test_the_result_shows_its_completed_time_in_site_time_not_the_browsers(
    import_world: SimpleNamespace,
):
    """The completed time used to be a `<time x-data="localTime">` the browser
    rewrote into its own zone, so it disagreed with the tables beside it."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert page.cssselect('time[x-data="localTime"]') == []
    assert len(page.cssselect("time[datetime]")) == 1


@pytest.mark.django_db
def test_a_second_confirmation_does_not_run_the_import_again(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    import_world.client.post(url)
    second = import_world.client.post(url)

    assert second.status_code == 303
    assert second["Location"] == _import_url(
        import_world.organisation, "learner_import_result", learner_import
    )
    assert Learner.objects.filter(organisation=import_world.organisation).count() == 3


@pytest.mark.django_db
def test_a_finished_import_redirects_from_its_preview_to_its_result(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(status=RunStatus.DONE)

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    assert response.status_code == 303


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["learner_import_preview", "learner_import_result"])
def test_an_import_is_a_404_for_another_user_of_the_organisation(
    import_world: SimpleNamespace, name: str
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    other = cast(User, UserFactory(superuser=True))

    response = import_world.logged_in_client(other).get(
        _import_url(import_world.organisation, name, learner_import)
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["learner_import_preview", "learner_import_result"])
def test_an_import_is_a_404_through_another_organisations_slug(
    import_world: SimpleNamespace, name: str
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    elsewhere = OrganisationFactory()

    response = import_world.client.get(_import_url(elsewhere, name, learner_import))

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_learners_list_offers_the_import_link_to_an_admin_and_not_to_a_cohort_admin(
    import_world: SimpleNamespace,
):
    url = _interface_url(import_world.organisation.slug, "learners")
    import_url = _import_url(import_world.organisation, "learner_import")

    admin_page = import_world.client.get(url).content.decode()
    cohort_admin_page = import_world.cohort_admin_client.get(url).content.decode()

    assert f'href="{import_url}"' in admin_page
    assert import_url not in cohort_admin_page


# learner import preview, template and error file


def _numbered_lines(good: int, bad: int) -> list[str]:
    return [f"person{n}@example.com,,," for n in range(good)] + [
        f"bad{n},,," for n in range(bad)
    ]


@pytest.mark.django_db
def test_the_preview_filters_its_rows_to_the_label_in_the_query_string(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "good@example.com,,,",
        "bad,,,",
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
        + "?label=error",
    )

    emails = [
        cell.text
        for cell in page.cssselect("[data-import-rows] tbody tr td:nth-child(2)")
    ]
    assert emails == ["bad"]


@pytest.mark.django_db
def test_each_label_count_links_to_the_preview_filtered_by_that_label(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    page = _get_document(import_world.client, preview_url)

    hrefs = [link.get("href") for link in page.cssselect("a[data-label-filter]")]
    assert sorted(hrefs) == [
        f"{preview_url}?label=error",
        f"{preview_url}?label=new_account",
    ]


@pytest.mark.django_db
def test_each_summary_tile_names_its_label_and_count_in_its_aria_label(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    labels = sorted(
        link.get("aria-label") for link in page.cssselect("a[data-label-filter]")
    )
    assert labels == ["Error: 1", "New account: 1"]


@pytest.mark.django_db
def test_only_the_tile_of_the_active_filter_is_marked_current(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
        + "?label=error",
    )

    current = {
        link.get("aria-label"): link.get("aria-current")
        for link in page.cssselect("a[data-label-filter]")
    }
    assert current == {"Error: 1": "true", "New account: 1": None}


@pytest.mark.django_db
def test_clear_filter_shows_only_under_a_filter_and_links_to_the_preview(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    unfiltered = _get_document(import_world.client, preview_url)
    filtered = _get_document(import_world.client, preview_url + "?label=error")

    clear = "//a[normalize-space()='Clear filter']"
    assert unfiltered.xpath(clear) == []
    assert [link.get("href") for link in filtered.xpath(clear)] == [preview_url]


@pytest.mark.django_db
def test_each_label_cell_carries_the_tone_of_its_label(import_world: SimpleNamespace):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "new@example.com,,,",
        f"{existing.user.email},,,",
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    tones = {
        row.xpath("string(td[2])").strip(): row.xpath("td[6]")[0].get("data-tone")
        for row in page.cssselect("[data-import-rows] tbody tr")
    }
    assert tones == {
        "new@example.com": PREVIEW_LABEL_TONES[ImportLabel.NEW_ACCOUNT],
        existing.user.email: PREVIEW_LABEL_TONES[ImportLabel.ALREADY_MEMBER],
    }


@pytest.mark.django_db
def test_the_preview_pages_fifty_rows_at_a_time_and_keeps_the_label_filter(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(2, 51)
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    first = _get_document(import_world.client, f"{preview_url}?label=error")
    second = _get_document(import_world.client, f"{preview_url}?label=error&page=2")

    next_link = next(
        link for link in first.cssselect("a") if link.text_content().strip() == "Next"
    )
    assert (
        len(first.cssselect("[data-import-rows] tbody tr")),
        len(second.cssselect("[data-import-rows] tbody tr")),
        sorted(parse_qsl(urlsplit(next_link.get("href")).query)),
    ) == (50, 1, [("label", "error"), ("page", "2")])


@pytest.mark.django_db
def test_an_htmx_page_request_for_the_preview_returns_only_the_rows_card(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(2, 51)
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    response = import_world.client.get(
        f"{preview_url}?label=error&page=2",
        headers={"HX-Request": "true", "HX-Target": "import-rows"},
    )

    page = lxml.html.fromstring(response.content.decode())
    assert len(page.cssselect("[data-import-rows] tbody tr")) == 1
    assert not page.cssselect("[data-label-filter]")


def _rows_footer_count(page: lxml.html.HtmlElement) -> str:
    (count,) = page.cssselect("#import-rows [data-entry-count]")
    return str(count.text_content()).strip()


@pytest.mark.django_db
def test_a_one_page_preview_states_how_many_rows_it_shows_in_its_footer(
    import_world: SimpleNamespace,
):
    """The Rows table used to have no footer at all on a single page."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(28, 0)
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert _rows_footer_count(page) == "28 rows"
    assert not page.cssselect("#import-rows a[hx-get]")


@pytest.mark.django_db
def test_a_two_page_preview_footer_shows_the_range_and_the_pager(
    import_world: SimpleNamespace,
):
    """The footer used to read only "Page 1 of 2", with no entry count."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(60, 0)
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert _rows_footer_count(page) == "Showing 1\u201350 of 60 rows"
    assert any(
        link.text_content().strip() == "Next"
        for link in page.cssselect("#import-rows a")
    )


@pytest.mark.django_db
def test_a_filtered_preview_footer_counts_the_filtered_rows(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(5, 3)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
        + "?label=error",
    )

    assert _rows_footer_count(page) == "3 rows"


@pytest.mark.django_db
def test_the_preview_rows_table_scrolls_inside_a_capped_region(
    import_world: SimpleNamespace,
):
    """The Rows table used to grow the page by up to fifty rows."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(3, 0)
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    assert page.cssselect("#import-rows [data-capped]")


@pytest.mark.django_db
def test_an_htmx_request_for_the_preview_from_elsewhere_returns_the_whole_preview(
    import_world: SimpleNamespace,
):
    """htmx following a redirect here, or a navigation link, swaps the main
    content, so it needs the tiles and the confirm form as well as the rows."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(2, 3)
    )
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    response = import_world.client.get(
        preview_url, headers={"HX-Request": "true", "HX-Target": "main-content"}
    )

    page = lxml.html.fromstring(response.content.decode())
    assert page.cssselect("[data-label-filter]")


@pytest.mark.django_db
def test_the_preview_shows_the_file_chip_and_a_link_to_upload_a_different_file(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    chip = " ".join(page.cssselect(".chip")[0].text_content().split())
    upload_link = page.xpath("//a[normalize-space()='Upload a different file']")[0]
    assert (chip, upload_link.get("href")) == (
        "learners.csv \u00b7 1 row",
        _import_url(import_world.organisation, "learner_import"),
    )


@pytest.mark.django_db
def test_the_preview_offers_each_row_as_a_card_for_narrow_screens(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,Ada,,"
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    card = page.cssselect("ul[data-row-cards] > li")[0]
    assert "a@example.com" in card.text_content()
    assert "New account" in card.text_content()


@pytest.mark.django_db
def test_the_preview_links_to_the_error_rows_download_only_when_there_are_errors(
    import_world: SimpleNamespace,
):
    with_errors = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,", "bad,,,"
    )
    without_errors = _import_for(
        import_world.admin, import_world.organisation, "b@example.com,,,"
    )

    def download_links(learner_import: LearnerImport) -> list[str]:
        page = _get_document(
            import_world.client,
            _import_url(
                import_world.organisation, "learner_import_preview", learner_import
            ),
        )
        return [
            " ".join(a.text_content().split())
            for a in page.cssselect("a[data-error-download]")
        ]

    assert (download_links(with_errors), download_links(without_errors)) == (
        ["Download errors"],
        [],
    )


def _preview_page(
    import_world: SimpleNamespace, learner_import: LearnerImport, query: str = ""
):
    return _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
        + query,
    )


@pytest.mark.django_db
def test_the_unfiltered_preview_rows_table_holds_no_error_rows(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    emails = [
        c.text for c in page.cssselect("[data-import-rows] tbody tr td:nth-child(2)")
    ]
    assert emails == ["good@example.com"]


@pytest.mark.django_db
def test_the_preview_filtered_to_errors_lists_only_error_rows_in_the_rows_table(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import, "?label=error")

    emails = [
        c.text for c in page.cssselect("[data-import-rows] tbody tr td:nth-child(2)")
    ]
    assert emails == ["bad"]


@pytest.mark.django_db
def test_the_error_block_lists_the_line_email_and_reason_of_each_error_row(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    cells = [
        c.text for c in page.cssselect("[data-error-block] table[data-error-rows] td")
    ]
    assert cells == ["3", "bad", "This isn't a valid email address."]


@pytest.mark.django_db
def test_the_error_block_links_to_the_download_and_the_corrected_file_upload(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    download = page.cssselect("[data-error-block] a[data-error-download]")[0]
    reupload = page.cssselect("[data-error-block] a[data-error-reupload]")[0]
    assert (download.get("href"), reupload.get("href")) == (
        _import_url(import_world.organisation, "learner_import_errors", learner_import),
        _import_url(import_world.organisation, "learner_import"),
    )


@pytest.mark.django_db
def test_the_error_block_buttons_are_the_small_size(import_world: SimpleNamespace):
    """The download and corrected-file links used to render at the default button size."""
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    buttons = page.cssselect(
        "[data-error-block] a[data-error-download], [data-error-block] a[data-error-reupload]"
    )
    assert [("btn-sm" in b.get("class").split()) for b in buttons] == [True, True]


@pytest.mark.django_db
def test_the_error_block_shows_fifty_error_rows_and_says_how_many_there_are(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(1, 51)
    )

    page = _preview_page(import_world, learner_import)

    block = page.cssselect("[data-error-block]")[0]
    assert len(block.cssselect("table[data-error-rows] tbody tr")) == 50
    assert "Showing the first 50 of 51." in " ".join(block.text_content().split())


@pytest.mark.django_db
def test_a_preview_without_errors_has_no_error_block(import_world: SimpleNamespace):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,"
    )

    page = _preview_page(import_world, learner_import)

    assert not page.cssselect("[data-error-block]")


@pytest.mark.django_db
def test_the_setup_email_line_is_absent_when_no_new_accounts_will_be_made(
    import_world: SimpleNamespace,
):
    existing = LearnerFactory(organisation=import_world.organisation)
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        f"{existing.user.email},,,",
        "bad,,,",
    )

    page = _preview_page(import_world, learner_import)

    assert "will get a setup email" not in page.text_content()


@pytest.mark.django_db
def test_an_all_errors_preview_has_no_rows_card_and_offers_a_different_file_button(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "bad,,,"
    )

    page = _preview_page(import_world, learner_import)

    buttons = page.cssselect("#main-content a.btn")
    different = [
        b
        for b in buttons
        if " ".join(b.text_content().split()) == "Upload a different file"
    ]
    assert not page.cssselect("[data-import-rows]")
    assert "Nothing can be added" in page.text_content()
    upload_url = _import_url(import_world.organisation, "learner_import")
    assert [b.get("href") for b in different] == [upload_url, upload_url]
    assert different[-1].xpath("ancestor::*[@data-error-block]") == []


@pytest.mark.django_db
def test_the_template_download_is_a_bom_prefixed_csv_with_the_headers_and_two_examples(
    import_world: SimpleNamespace,
):
    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_template")
    )

    body = b"".join(response.streaming_content).decode("utf-8")
    rows = list(csv.reader(io.StringIO(body.lstrip("﻿"))))
    assert (
        body.startswith("﻿"),
        response["Content-Disposition"],
        rows[0],
        len(rows),
    ) == (
        True,
        'attachment; filename="learner-import-template.csv"',
        ["email", "first_name", "last_name", "cohort"],
        3,
    )


@pytest.mark.django_db
def test_the_template_download_is_refused_to_a_user_who_fails_the_import_gate(
    import_world: SimpleNamespace,
):
    response = import_world.cohort_admin_client.get(
        _import_url(import_world.organisation, "learner_import_template")
    )

    assert response.status_code == 403


@pytest.fixture
def cohort_importer_client(
    import_world: SimpleNamespace, mock_site_context: Site, settings
) -> Iterator[Client]:
    """A client whose user passes the cohort import gate but not the
    organisation-wide one, which no shipped role does."""
    role = Role(
        display_name="Cohort importer",
        permissions=frozenset(
            {
                VIEW_ORGANISATION,
                VIEW_COHORT,
                VIEW_LEARNER,
                ADD_LEARNER,
                ADD_COHORTMEMBERSHIP,
            }
        ),
        assignment_scope=SCOPE_OBJECT,
    )
    with custom_role_config(
        mock_site_context, settings, extra_roles={"cohort_importer": role}
    ):
        importer = cast(
            User,
            LearnerFactory(
                user__staff=True, organisation=import_world.organisation
            ).user,
        )
        assign_object_role(importer, import_world.organisation, "cohort_importer")
        yield import_world.logged_in_client(importer)


@pytest.mark.django_db
def test_a_cohort_page_importer_can_download_the_template(
    import_world: SimpleNamespace, cohort_importer_client: Client
):
    """The template was gated on the organisation-wide import, so the cohort
    upload page offered a link that answered 403 to an importer who may only
    import into the cohort."""
    upload_url = (
        f"{_import_url(import_world.organisation, 'learner_import')}"
        f"?cohort={import_world.cohort.pk}"
    )
    page = _get_document(cohort_importer_client, upload_url)
    template_url = _import_url(import_world.organisation, "learner_import_template")
    (href,) = [
        a.get("href") for a in page.cssselect("a") if template_url in a.get("href")
    ]

    organisation_wide = cohort_importer_client.get(template_url)
    response = cohort_importer_client.get(href)

    assert href == f"{template_url}?cohort={import_world.cohort.pk}"
    assert organisation_wide.status_code == 403
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")


@pytest.mark.django_db
def test_the_upload_page_links_to_the_template(import_world: SimpleNamespace):
    page = _get_document(
        import_world.client, _import_url(import_world.organisation, "learner_import")
    )

    hrefs = [a.get("href") for a in page.cssselect("a")]
    assert _import_url(import_world.organisation, "learner_import_template") in hrefs


def _error_csv_rows(response) -> tuple[str, list[list[str]]]:
    body = b"".join(response.streaming_content).decode("utf-8")
    return body, list(csv.reader(io.StringIO(body.lstrip("﻿"))))


@pytest.mark.django_db
def test_the_error_csv_of_a_preview_holds_exactly_the_error_rows_with_reasons(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin,
        import_world.organisation,
        "good@example.com,Ada,Lovelace,",
        "=bad,Eve,Hacker,",
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_errors", learner_import)
    )

    body, rows = _error_csv_rows(response)
    assert (body.startswith("﻿"), rows) == (
        True,
        [
            ["email", "first_name", "last_name", "cohort", "reason"],
            ["'=bad", "Eve", "Hacker", "", "This isn't a valid email address."],
        ],
    )


@pytest.mark.django_db
def test_the_error_csv_is_named_for_the_day(import_world: SimpleNamespace):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "bad,,,"
    )

    with time_machine.travel(datetime(2026, 3, 4, 12, tzinfo=UTC)):
        response = import_world.client.get(
            _import_url(
                import_world.organisation, "learner_import_errors", learner_import
            )
        )

    assert (
        response["Content-Disposition"]
        == 'attachment; filename="learner-import-errors-2026-03-04.csv"'
    )


@pytest.mark.django_db
def test_the_error_csv_of_a_finished_import_holds_the_final_error_rows(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_errors", learner_import)
    )

    _body, rows = _error_csv_rows(response)
    assert [row[0] for row in rows[1:]] == ["bad"]


@pytest.mark.django_db
def test_the_error_csv_is_a_404_for_another_user_of_the_organisation(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "bad,,,"
    )
    other = cast(User, UserFactory(superuser=True))

    response = import_world.logged_in_client(other).get(
        _import_url(import_world.organisation, "learner_import_errors", learner_import)
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_result_lists_its_error_rows_the_download_and_the_reupload_line(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    text = " ".join(page.text_content().split())
    error_cells = [cell.text for cell in page.cssselect("table[data-error-rows] td")]
    download = page.cssselect("a[data-error-download]")[0].get("href")
    assert (error_cells, download) == (
        ["3", "bad", "This isn't a valid email address."],
        _import_url(import_world.organisation, "learner_import_errors", learner_import),
    )
    assert (
        "Uploading the whole file again is safe: rows already added show as "
        "'already a member'." in text
    )


@pytest.mark.django_db
def test_the_result_shows_only_the_first_fifty_error_rows(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, *_numbered_lines(0, 51)
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert len(page.cssselect("table[data-error-rows] tbody tr")) == 50
    assert "Showing the first 50 of 51." in " ".join(page.text_content().split())


@pytest.mark.django_db
def test_the_result_error_block_has_no_corrected_file_link(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "good@example.com,,,", "bad,,,"
    )
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert page.cssselect("[data-error-block]")
    assert not page.cssselect("a[data-error-reupload]")


@pytest.mark.django_db
def test_a_failed_import_shows_the_reupload_line(import_world: SimpleNamespace):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(
        status=RunStatus.FAILED, error_message="Something broke."
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    assert "Uploading the whole file again is safe" in page.text_content()


def _import_task_rows():
    from django_tasks_db.models import DBTaskResult

    return DBTaskResult.objects.filter(task_path__endswith="_run_learner_import_task")


def _ten_row_import(import_world: SimpleNamespace) -> LearnerImport:
    return _import_for(
        import_world.admin,
        import_world.organisation,
        *(f"learner{index}@example.com,,," for index in range(10)),
    )


@pytest.mark.django_db
def test_the_preview_names_the_background_only_above_the_threshold(
    import_world: SimpleNamespace, settings
):
    learner_import = _ten_row_import(import_world)
    url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    settings.BULK_BACKGROUND_THRESHOLD = 10
    at_threshold = " ".join(
        _get_document(import_world.client, url).text_content().split()
    )
    settings.BULK_BACKGROUND_THRESHOLD = 9
    above_threshold = " ".join(
        _get_document(import_world.client, url).text_content().split()
    )

    assert "runs in the background" not in at_threshold
    assert (
        "This import runs in the background. The result page will show progress."
        in above_threshold
    )


@pytest.mark.django_db(transaction=True)
def test_confirming_above_the_threshold_queues_one_task_and_the_result_page_polls(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    preview_url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )
    result_url = _import_url(
        import_world.organisation, "learner_import_result", learner_import
    )

    confirmed = import_world.client.post(preview_url)
    page = _get_document(import_world.client, result_url)

    learner_import.refresh_from_db()
    (status,) = page.cssselect("#run-status")
    assert (confirmed.status_code, confirmed["Location"]) == (303, result_url)
    assert learner_import.status == RunStatus.QUEUED
    assert _import_task_rows().count() == 1
    assert Learner.objects.filter(organisation=import_world.organisation).count() == 2
    assert status.get("role") == "status"
    assert status.get("hx-trigger") == "every 2s"
    assert status.get("hx-get") == _import_url(
        import_world.organisation, "learner_import_status", learner_import
    )
    assert "Waiting to start." in status.text_content()
    assert status.cssselect("progress, [role=progressbar]")


@pytest.mark.django_db(transaction=True)
def test_a_second_confirmation_of_a_queued_import_does_not_enqueue_again(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    url = _import_url(
        import_world.organisation, "learner_import_preview", learner_import
    )

    import_world.client.post(url)
    second = import_world.client.post(url)

    assert second.status_code == 303
    assert second["Location"] == _import_url(
        import_world.organisation, "learner_import_result", learner_import
    )
    assert _import_task_rows().count() == 1


@pytest.mark.django_db(transaction=True)
def test_the_status_partial_drops_the_trigger_and_holds_the_result_once_done(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )
    status_url = _import_url(
        import_world.organisation, "learner_import_status", learner_import
    )

    queued = import_world.client.get(status_url)
    run_learner_import(str(learner_import.pk), import_world.organisation.site_id)
    done = import_world.client.get(status_url)

    queued_status = lxml.html.fromstring(queued.content.decode())
    done_status = lxml.html.fromstring(done.content.decode())
    assert queued_status.get("hx-trigger") == "every 2s"
    assert done_status.get("id") == "run-status"
    assert done_status.get("hx-trigger") is None
    assert done_status.get("hx-get") is None
    assert "Added 10 learners." in " ".join(done_status.text_content().split())


@pytest.mark.django_db
def test_the_status_partial_of_a_failed_import_stops_polling_and_shows_the_reason(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(
        status=RunStatus.FAILED, error_message="Something broke.", processed_count=0
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )

    status = lxml.html.fromstring(response.content.decode())
    text = " ".join(status.text_content().split())
    assert status.get("hx-trigger") is None
    assert "Stopped after 0 of 1 rows" in text
    assert "Something broke." in text
    assert "Uploading the whole file again is safe" in text


def _finished_result_page(
    import_world: SimpleNamespace, *lines: str
) -> lxml.html.HtmlElement:
    learner_import = _import_for(import_world.admin, import_world.organisation, *lines)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )
    return _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )


@pytest.mark.django_db
def test_a_result_with_no_rows_lost_does_not_mention_rows_not_added(
    import_world: SimpleNamespace,
):
    page = _finished_result_page(import_world, "a@example.com,,,", "b@example.com,,,")

    text = " ".join(page.text_content().split())
    assert "Added 2 learners." in text
    assert "was not added" not in text
    assert "were not added" not in text


@pytest.mark.django_db
def test_a_result_with_no_new_accounts_has_no_setup_email_text(
    import_world: SimpleNamespace,
):
    page = _finished_result_page(import_world, "nonsense,,,")

    assert "setup email" not in page.text_content()


@pytest.mark.django_db
def test_a_result_shows_the_summary_and_the_error_rows_in_separate_panels(
    import_world: SimpleNamespace,
):
    page = _finished_result_page(import_world, "a@example.com,,,", "nonsense,,,")

    (summary,) = page.cssselect("#run-status .panel-surface")
    (error_block,) = page.cssselect("#run-status [data-error-block]")
    assert "Added 1 learner." in summary.text_content()
    assert not summary.cssselect("[data-error-block]")
    assert not [a for a in error_block.iterancestors() if "panel-surface" in a.classes]


@pytest.mark.django_db
def test_a_finished_result_has_no_importing_heading_and_focuses_its_heading(
    import_world: SimpleNamespace,
):
    page = _finished_result_page(import_world, "a@example.com,,,")

    (heading,) = page.cssselect("#run-status h2")
    assert "Importing learners" not in page.text_content()
    assert heading.get("autofocus") is not None
    assert heading.get("tabindex") == "-1"


@pytest.mark.django_db(transaction=True)
def test_a_running_result_is_headed_importing_learners_and_keeps_its_poll(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    (status,) = page.cssselect("#run-status")
    headings = [h.text_content().strip() for h in page.cssselect("#main-content h2")]
    assert "Importing learners" in headings
    assert status.get("role") == "status"
    assert status.get("hx-trigger") == "every 2s"
    assert "Waiting to start." in status.text_content()
    assert status.cssselect("progress, [role=progressbar]")


@pytest.mark.django_db(transaction=True)
def test_the_status_fragment_has_no_refresh_header_while_queued(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )

    assert "HX-Refresh" not in response


@pytest.mark.django_db(transaction=True)
def test_the_status_fragment_asks_for_a_page_refresh_once_done(
    import_world: SimpleNamespace, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 5
    learner_import = _ten_row_import(import_world)
    import_world.client.post(
        _import_url(import_world.organisation, "learner_import_preview", learner_import)
    )
    run_learner_import(str(learner_import.pk), import_world.organisation.site_id)

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )

    assert response["HX-Refresh"] == "true"


@pytest.mark.django_db
def test_the_status_fragment_asks_for_a_page_refresh_once_failed(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(
        status=RunStatus.FAILED, error_message="Something broke."
    )

    response = import_world.client.get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )

    assert response["HX-Refresh"] == "true"


@pytest.mark.django_db
def test_the_import_status_is_a_404_for_another_user_and_another_organisation(
    import_world: SimpleNamespace,
):
    learner_import = _import_for(
        import_world.admin, import_world.organisation, "a@example.com,,,"
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(status=RunStatus.QUEUED)
    other = cast(User, UserFactory(superuser=True))

    by_other_user = import_world.logged_in_client(other).get(
        _import_url(import_world.organisation, "learner_import_status", learner_import)
    )
    through_other_slug = import_world.client.get(
        _import_url(OrganisationFactory(), "learner_import_status", learner_import)
    )

    assert by_other_user.status_code == 404
    assert through_other_slug.status_code == 404


# learner import from a cohort


def _cohort_import_url(organisation: Organisation, cohort: Cohort) -> str:
    return f"{_import_url(organisation, 'learner_import')}?cohort={cohort.pk}"


def _learners_tab_url(organisation: Organisation, cohort: Cohort) -> str:
    return _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners")


@pytest.mark.django_db
def test_the_cohort_upload_page_names_the_cohort_and_says_the_cohort_column_is_ignored(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation, name="Accra Jan")

    page = _get_document(
        import_world.client, _cohort_import_url(import_world.organisation, cohort)
    )

    text = " ".join(page.text_content().split())
    assert "Accra Jan" in text
    assert "The cohort column is ignored" in text
    assert "is matched by name" not in text


@pytest.mark.django_db
def test_a_cohort_admin_gets_the_403_page_from_the_cohort_upload_page(
    import_world: SimpleNamespace,
):
    response = import_world.cohort_admin_client.get(
        _cohort_import_url(import_world.organisation, import_world.cohort)
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_inactive_cohort_is_refused_by_the_cohort_upload_page(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation, is_active=False)

    response = import_world.client.get(
        _cohort_import_url(import_world.organisation, cohort)
    )

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cohort_param", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"]
)
def test_an_unknown_cohort_is_a_404_on_the_upload_page(
    import_world: SimpleNamespace, cohort_param: str
):
    response = import_world.client.get(
        f"{_import_url(import_world.organisation, 'learner_import')}?cohort={cohort_param}"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_cohort_in_another_organisation_is_a_404_on_the_upload_page(
    import_world: SimpleNamespace,
):
    foreign = CohortFactory(organisation=OrganisationFactory())

    response = import_world.client.get(
        _cohort_import_url(import_world.organisation, foreign)
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_uploading_from_the_cohort_page_stores_the_cohort_on_the_import(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation)

    response = import_world.client.post(
        _cohort_import_url(import_world.organisation, cohort),
        {"file": _csv_upload("a@example.com,Ada,Lovelace,Other cohort")},
    )

    learner_import = LearnerImport.objects.get()
    assert response.status_code == 303
    assert learner_import.cohort == cohort


@pytest.mark.django_db
def test_the_preview_of_a_cohort_import_shows_the_target_cohort_on_every_row(
    import_world: SimpleNamespace,
):
    """The preview echoed the file's ignored cohort cell, so a row naming
    another cohort, or none, looked like it would join somewhere else."""
    cohort = CohortFactory(organisation=import_world.organisation, name="Target A")
    CohortFactory(organisation=import_world.organisation, name="Other C")
    learner_import = create_learner_import(
        import_world.admin,
        import_world.organisation,
        cohort,
        _csv_upload("a@example.com,Co,Imp,Other C", "b@example.com,,,"),
    )

    page = _get_document(
        import_world.client,
        _import_url(
            import_world.organisation, "learner_import_preview", learner_import
        ),
    )

    table_cells = [
        " ".join(row.cssselect("td")[4].text_content().split())
        for row in page.cssselect("[data-import-rows] tbody tr")
    ]
    card_values = [
        " ".join(dd.text_content().split())
        for dd in page.cssselect("[data-row-cards] dt:contains('Cohort') + dd")
    ]
    assert table_cells == ["Target A", "Target A"]
    assert card_values == ["Target A", "Target A"]


@pytest.mark.django_db
def test_a_failed_cohort_upload_keeps_the_cohort_for_the_next_attempt(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation, name="Accra Jan")

    response = import_world.client.post(
        _cohort_import_url(import_world.organisation, cohort),
        {"file": SimpleUploadedFile("learners.csv", b"name\nAda\n")},
    )

    assert response.status_code == 422
    assert "Accra Jan" in response.content.decode()


@pytest.mark.django_db
def test_the_result_of_a_cohort_import_links_to_the_cohorts_learners_tab(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation)
    learner_import = create_learner_import(
        import_world.admin,
        import_world.organisation,
        cohort,
        _csv_upload("a@example.com,,,"),
    )
    LearnerImport.objects.filter(pk=learner_import.pk).update(
        status=ImportStatus.QUEUED
    )
    run_learner_import(str(learner_import.pk), import_world.organisation.site_id)

    page = _get_document(
        import_world.client,
        _import_url(import_world.organisation, "learner_import_result", learner_import),
    )

    hrefs = [link.get("href") for link in page.cssselect("#main-content a")]
    assert _learners_tab_url(import_world.organisation, cohort) in hrefs


@pytest.mark.django_db
def test_the_cohort_learners_tab_offers_the_import_link_to_an_organisation_admin(
    import_world: SimpleNamespace,
):
    cohort = CohortFactory(organisation=import_world.organisation)

    page = _get_document(
        import_world.client, _learners_tab_url(import_world.organisation, cohort)
    )

    hrefs = [link.get("href") for link in page.cssselect("a[href]")]
    assert _cohort_import_url(import_world.organisation, cohort) in hrefs


@pytest.mark.django_db
def test_the_cohort_learners_tab_hides_the_import_link_from_a_cohort_admin(
    import_world: SimpleNamespace,
):
    page = _get_document(
        import_world.cohort_admin_client,
        _learners_tab_url(import_world.organisation, import_world.cohort),
    )

    hrefs = [link.get("href") or "" for link in page.cssselect("a[href]")]
    assert not [href for href in hrefs if "/learners/import" in href]


EDUCATOR_TABLES: list[type[DataTable]] = [
    LearnerDataTable,
    CohortLearnerDataTable,
    CohortDataTable,
    LearnerCohortDataTable,
    CourseDataTable,
    educator_views.CohortCourseRegistrationDataTable,
    CourseCohortRegistrationDataTable,
    CourseLearnerRegistrationDataTable,
    StaffDataTable,
    OrganisationAuditLogTable,
]


@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_the_first_use_message_is_a_sentence(table: type[DataTable]) -> None:
    assert table.empty_message.endswith(".")
    assert table.empty_message != DataTable.empty_message


@pytest.mark.parametrize(
    "panel", [LearnerHistoryPanel, educator_views.CohortHistoryPanel]
)
def test_a_history_panel_says_what_will_be_recorded(panel: type) -> None:
    assert panel.empty_message.endswith(".")
    assert panel.data_table.empty_no_results.endswith(".")


@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_the_no_results_message_is_a_sentence(table: type[DataTable]) -> None:
    assert table.empty_no_results.endswith(".")


@pytest.mark.django_db
@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_a_filter_in_play_offers_to_clear_it(
    table: type[DataTable], mock_site_context: Site
) -> None:
    html = render_to_string(
        "panel_framework/partials/table_empty.html",
        {
            "any_filter_set": True,
            "empty_no_results": table.empty_no_results,
            "empty_message": table.empty_message,
            "clear_changes": {},
            "clear_search_changes": {},
            "page_url": "/x/",
            "base_url": "/x/",
            "region_id": "r",
        },
        request=RequestFactory().get("/x/"),
    )

    assert table.empty_no_results in html
    assert table.empty_message not in html
    assert "Clear filters" in html


def _cohort_entry(cohort: Cohort, **overrides: object) -> AuditLogEntry:
    return cast(
        AuditLogEntry,
        AuditLogEntryFactory(
            target=cohort,
            organisation=cohort.organisation,
            action="cohort.updated",
            **overrides,
        ),
    )


def _cohort_history_url(cohort: Cohort) -> str:
    return _interface_url(
        cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history"
    )


@pytest.mark.django_db
def test_the_cohort_history_export_holds_only_entries_naming_the_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    other = CohortFactory(organisation=organisation)
    for number in range(30):
        _cohort_entry(cohort, reason=f"reason {number}")
    _cohort_entry(other, reason="not ours")

    _header, rows, _disposition = _export_audit_csv(
        staff_client, _cohort_history_url(cohort)
    )

    assert (len(rows), "not ours" in {row[7] for row in rows}) == (30, False)


@pytest.mark.django_db
def test_the_cohort_history_export_is_named_for_the_cohort(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Spring Intake")
    _cohort_entry(cohort)

    _header, _rows, disposition = _export_audit_csv(
        staff_client, _cohort_history_url(cohort)
    )

    assert disposition == (
        f'attachment; filename="history-spring-intake-{timezone.localdate():%Y-%m-%d}.csv"'
    )


@pytest.mark.django_db
def test_the_cohort_history_export_records_an_entry_for_the_audit_log_only(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Spring Intake")
    _cohort_entry(cohort)

    _export_audit_csv(staff_client, _cohort_history_url(cohort))

    entry = AuditLogEntry.objects.get(action="audit_log.exported")
    audit_rows = _audit_log_rows(
        _get_document(staff_client, _audit_log_url(organisation))
    )
    history_rows = _history_rows(_cohort_history_tab(staff_client, cohort))
    assert (
        entry.details,
        len([row for row in audit_rows if "Audit log exported" in row[2]]),
        len(history_rows),
    ) == (
        {
            "scope": "cohort",
            "scope_label": "Spring Intake",
            "count": 1,
            "filters": "",
        },
        1,
        1,
    )


@pytest.mark.django_db
def test_the_cohort_history_toolbar_offers_the_csv_export(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    _cohort_entry(cohort)

    document = _cohort_history_tab(staff_client, cohort)

    links = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert links
    assert all("history-export=csv" in a.get("href") for a in links)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "target"),
    [
        ("cohort_admin", "audit_log"),
        ("cohort_viewer", "cohort_history"),
        ("cohort_viewer", "audit_log"),
    ],
)
def test_a_cohort_role_gets_a_404_on_the_exports_it_may_not_read(
    mock_site_context, logged_in_client, role: str, target: str
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, role, cohort)
    url, key = (
        (_cohort_history_url(cohort), "history-export")
        if target == "cohort_history"
        else (_audit_log_url(organisation), "audit_log-export")
    )

    response = logged_in_client(educator).get(url, {key: "csv"})

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_cohort_admin_exports_the_history_of_a_cohort_they_administer(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = logged_in_client(educator).get(
        _cohort_history_url(cohort), {"history-export": "csv"}
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")


# Profile pictures on the learners table, course registrations table, cohort settings panel and audit log.

PictureSurface = Callable[[Organisation, User], str]


def _learners_table(organisation: Organisation, person: User) -> str:
    LearnerFactory(organisation=organisation, user=person)
    return get_interface_page(
        organisation, "learners", organisation_admin_viewer(organisation)
    )


def _registrations_table(organisation: Organisation, person: User) -> str:
    course = CourseFactory()
    learner = LearnerFactory(organisation=organisation, user=person)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    return get_interface_page(
        organisation,
        f"courses/{course.pk}/__panels/learners",
        organisation_admin_viewer(organisation),
    )


def _cohort_settings(organisation: Organisation, person: User) -> str:
    cohort = CohortFactory(organisation=organisation)
    assign_role(UserFactory(superuser=True), person, "cohort_admin", cohort)
    return get_interface_page(
        organisation,
        f"cohorts/{cohort.pk}/__tabs/settings",
        organisation_admin_viewer(organisation),
    )


PICTURE_SURFACES = [
    pytest.param(_learners_table, id="learners-table"),
    pytest.param(_registrations_table, id="course-registrations-table"),
    pytest.param(_cohort_settings, id="cohort-settings"),
]


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
@pytest.mark.parametrize("surface", PICTURE_SURFACES)
def test_a_person_with_a_picture_shows_it(surface: PictureSurface) -> None:
    person = cast(User, UserFactory(with_profile_picture=True))

    content = surface(OrganisationFactory(), person)

    assert person.profile_picture_url in profile_picture_sources(content)


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
@pytest.mark.parametrize("surface", PICTURE_SURFACES)
def test_a_person_without_a_picture_shows_initials_alone(
    surface: PictureSurface,
) -> None:
    content = surface(OrganisationFactory(), cast(User, UserFactory()))

    assert profile_picture_sources(content) == []
    assert 'src="None"' not in content


def _add_learner_rows(organisation: Organisation, count: int) -> None:
    for _ in range(count):
        LearnerFactory(
            organisation=organisation, user=UserFactory(with_profile_picture=True)
        )


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_more_learner_rows_with_pictures_cost_no_more_queries(
    django_assert_max_num_queries,
) -> None:
    content = page_after_adding_rows(
        OrganisationFactory(),
        "learners",
        _add_learner_rows,
        django_assert_max_num_queries,
    )

    assert len(profile_picture_sources(content)) >= 5


@pytest.mark.django_db
def test_learners_list_names_the_owner_under_the_shared_course_entry_only(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
):
    """Two learners on same-titled courses showed one bare title each, with
    nothing to tell the shared course from the organisation's own."""
    organisation, own, shared = _shared_and_own_course_world()
    on_shared = LearnerFactory(
        user=UserFactory(first_name="Shared", last_name="Learner"),
        organisation=organisation,
    )
    on_own = LearnerFactory(
        user=UserFactory(first_name="Own", last_name="Learner"),
        organisation=organisation,
    )
    LearnerCourseRegistrationFactory(learner=on_shared, course=shared)
    LearnerCourseRegistrationFactory(learner=on_own, course=own)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(client, _interface_url(organisation.slug, "learners"))

    rows = _shared_by_notes_by_row(document)
    assert _notes_for(rows, "Shared Learner") == ["Shared by Northwind Logistics"]
    assert _notes_for(rows, "Own Learner") == []


@pytest.mark.django_db
def test_cohorts_list_names_the_owner_under_the_shared_course_only(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
):
    """The Courses column of the cohorts list gave a shared course and an own
    course of one title the same bare text."""
    organisation, own, shared = _shared_and_own_course_world()
    on_shared = CohortFactory(organisation=organisation, name="Shared cohort")
    on_own = CohortFactory(organisation=organisation, name="Own cohort")
    CohortCourseRegistrationFactory(cohort=on_shared, course=shared)
    CohortCourseRegistrationFactory(cohort=on_own, course=own)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(client, _interface_url(organisation.slug, "cohorts"))

    rows = _shared_by_notes_by_row(document)
    assert _notes_for(rows, "Shared cohort") == ["Shared by Northwind Logistics"]
    assert _notes_for(rows, "Own cohort") == []


@pytest.mark.django_db
def test_cohort_course_completion_names_the_owner_of_a_shared_course_only(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
):
    """The cohort's course completion rows named a shared course by its bare
    title."""
    organisation, own, shared = _shared_and_own_course_world()
    cohort = CohortFactory(organisation=organisation)
    CohortCourseRegistrationFactory(cohort=cohort, course=shared)
    CohortCourseRegistrationFactory(cohort=cohort, course=own)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(
        client,
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/overview"),
    )

    text = " ".join(document.text_content().split())
    assert text.count("Shared by Northwind Logistics") == 1
    assert "Shared by Northwind Logistics · 0 of 0 completed" in text
