"""The educator interface's section configs and the pages they render."""

from __future__ import annotations

import copy
import csv
import io
import json
import uuid
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qsl, quote, urlsplit
from uuid import uuid4

import lxml.html
import pytest
import time_machine

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.models import Model
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import (
    record_entry,
    record_run_summary,
    subject_key,
)
from freedom_ls.comms.factories import (
    ConversationFactory,
    MessageFactory,
    NotificationFactory,
)
from freedom_ls.comms.messaging import (
    SendResult,
    encode_cursor,
    inbox_for,
    unread_conversation_count,
)
from freedom_ls.comms.messaging_policy import MessagingRefusal
from freedom_ls.comms.models import Conversation, Message
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseCategoryFactory,
    CourseFactory,
    CoursePartFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course as CourseModel
from freedom_ls.educator_interface import views as educator_views
from freedom_ls.educator_interface.actions import DeactivateLearnersBulkAction
from freedom_ls.educator_interface.events import COHORT_CHANGED, LEARNER_CHANGED
from freedom_ls.educator_interface.learner_import import (
    PREVIEW_LABEL_TONES,
    create_learner_import,
    run_learner_import,
)
from freedom_ls.educator_interface.messaging import OwnConversation
from freedom_ls.educator_interface.tests.interface_walk import (
    WalkedPanel,
    walk_interface,
)
from freedom_ls.educator_interface.views import (
    CohortDataTable,
    active_status_badge,
    learner_status_badge,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormProgress, QuestionAnswer
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
    StaffMemberFactory,
)
from freedom_ls.learner_management.learner_actions import (
    add_to_cohort,
    move_between_cohorts,
    register_for_course,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    ImportLabel,
    ImportStatus,
    Learner,
    LearnerCourseRegistration,
    LearnerImport,
    StaffMember,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTMEMBERSHIP,
    ADD_LEARNER,
    VIEW_COHORT,
    VIEW_LEARNER,
    VIEW_ORGANISATION,
)
from freedom_ls.learner_management.role_assignment import GrantableRole, assign_role
from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.learner_management.utils import register_cohort_for_course
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.bulk_runs import run_bulk_action
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.reports.tests.helpers import topic_progress
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

QUERY_BUDGET = 60

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper

    from django.test.client import _MonkeyPatchedWSGIResponse


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
    for i in range(DataTable.page_size + 1):
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
    assert f"Learner{DataTable.page_size:02d}" in content
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


def _header_of(document: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (heading,) = document.cssselect("#instance-title")
    return heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]


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
def test_the_learner_settings_tab_offers_every_learner_action_to_an_org_admin(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/settings")

    (name,) = document.cssselect("section[data-panel='name']")
    (account,) = document.cssselect("section[data-panel='account']")
    labels = [
        button.text_content().strip() for button in account.cssselect("footer .btn")
    ]
    # The name is a field with Save on its own panel. Resend setup email is
    # offered only while the learner is pending. Add to cohort and Register
    # for a course sit with the cohorts and the courses.
    assert name.cssselect("form#learner-name-form")
    assert labels == ["Deactivate"]


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
def test_register_for_a_course_sits_on_the_learners_courses_tab(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/courses")

    (panel,) = document.cssselect("section[data-panel='courses']")
    labels = [
        button.text_content().strip() for button in panel.cssselect("footer .btn")
    ]
    assert labels == ["Register for a course"]


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
def test_course_page_buttons_are_only_preview_triggers(staff_client: Client):
    organisation = OrganisationFactory()
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(title="Intro"), order=0
    )

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    assert header.cssselect("button[hx-get]") == []
    buttons = document.cssselect("section[data-panel] button[hx-get]")
    assert [button.get("aria-label") for button in buttons] == [
        "Preview course details page",
        "Preview Intro",
    ]
    assert document.cssselect("section[data-panel] footer button") == []


def _course_details_text(client: Client, course: CourseModel) -> str:
    organisation = OrganisationFactory()
    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )
    (panel,) = document.cssselect("section[data-panel='details']")
    return " ".join(panel.text_content().split())


@pytest.mark.django_db
def test_course_details_show_each_set_field_with_the_learner_label(
    staff_client: Client,
):
    course = CourseFactory(
        title="Algebra",
        subtitle="Start here",
        difficulty="beginner",
        estimated_duration=timedelta(hours=2),
        time_limit_days=90,
        learning_outcomes=["Solve equations", "Plot graphs"],
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )

    text = _course_details_text(staff_client, course)

    for expected in (
        "Subtitle",
        "Start here",
        "Visibility",
        "Level",
        "Beginner",
        "Duration ~2 hours",
        "Time limit 90 days",
        "Solve equations",
        "Plot graphs",
        "Lessons 1",
    ):
        assert expected in text


@pytest.mark.django_db
def test_course_details_list_each_learning_outcome_on_its_own(
    staff_client: Client,
):
    """An outcome can hold a comma, so joining them with commas would lose
    where one ends and the next begins."""
    organisation = OrganisationFactory()
    course = CourseFactory(learning_outcomes=["Read, write and speak", "Plan"])

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )
    (panel,) = document.cssselect("section[data-panel='details']")

    items = [
        li.text_content().strip() for li in panel.cssselect("ul li > span:last-child")
    ]
    assert items == ["Read, write and speak", "Plan"]


@pytest.mark.django_db
def test_course_details_label_the_category_row_category(staff_client: Client):
    """The category row read "Dashboard category" (the model field's verbose
    name) instead of the learner page's word, "Category"."""
    course = CourseFactory(dashboard_category=CourseCategoryFactory(title="Maths"))

    text = _course_details_text(staff_client, course)

    assert "Category Maths" in text
    assert "Dashboard category" not in text


@pytest.mark.django_db
def test_course_details_leave_out_rows_without_a_value(staff_client: Client):
    course = CourseFactory(
        subtitle="",
        estimated_duration=None,
        time_limit_days=None,
        learning_outcomes=[],
    )

    text = _course_details_text(staff_client, course)

    for label in ("Subtitle", "Duration", "Time limit", "Learning outcomes"):
        assert label not in text
    assert "Lessons 0" in text


@pytest.mark.django_db
def test_course_details_lesson_count_reads_the_number_of_topics(
    staff_client: Client,
):
    course = CourseFactory()
    for order in range(3):
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(), order=order
        )

    assert "Lessons 3" in _course_details_text(staff_client, course)


def _cohort_table_request(
    site_aware_request: RequestFactory, organisation: Organisation, query_string: str
):
    request = site_aware_request.get(f"/?{query_string}")
    request.user = LearnerFactory(user__superuser=True).user
    request.organisation = organisation
    request.panel_url_kwargs = {"organisation_slug": organisation.slug}
    return request


def _cohort_names(
    site_aware_request: RequestFactory, organisation: Organisation, query_string: str
) -> list[str]:
    """The cohort names the list shows for ``query_string``, in row order."""
    request = _cohort_table_request(site_aware_request, organisation, query_string)
    query = CohortDataTable.parse_query(request, "cohorts")
    queryset = CohortDataTable.filter_queryset(
        request, CohortDataTable.get_queryset(request), query
    )
    return [cohort.name for cohort in queryset]


@pytest.mark.django_db
def test_cohort_list_search_matches_on_name(site_aware_request):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Morning group")
    CohortFactory(organisation=organisation, name="Evening group")

    names = _cohort_names(site_aware_request, organisation, "cohorts-q=morning")

    assert names == ["Morning group"]


@pytest.mark.django_db
def test_cohort_list_default_order_is_name_then_pk(site_aware_request):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Beta")
    CohortFactory(organisation=organisation, name="Alpha")

    names = _cohort_names(site_aware_request, organisation, "")

    assert names == ["Alpha", "Beta"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("name", ["Alpha", "Bravo", "Charlie"]),
        ("-name", ["Charlie", "Bravo", "Alpha"]),
        ("learner_count", ["Bravo", "Alpha", "Charlie"]),
        ("-learner_count", ["Charlie", "Alpha", "Bravo"]),
        ("created_at", ["Charlie", "Alpha", "Bravo"]),
        ("-created_at", ["Bravo", "Alpha", "Charlie"]),
    ],
)
def test_cohort_list_sorts_on_name_learners_and_created(
    site_aware_request, sort, expected
):
    organisation = OrganisationFactory()
    charlie = CohortFactory(organisation=organisation, name="Charlie")
    alpha = CohortFactory(organisation=organisation, name="Alpha")
    bravo = CohortFactory(organisation=organisation, name="Bravo")
    CohortMembershipFactory.create_batch(2, cohort=alpha)
    CohortMembershipFactory.create_batch(3, cohort=charlie)
    assert bravo.created_at > alpha.created_at > charlie.created_at

    names = _cohort_names(site_aware_request, organisation, f"cohorts-sort={sort}")

    assert names == expected


@pytest.mark.django_db
def test_cohort_list_learner_count_excludes_a_removed_learner(site_aware_request):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort)
    CohortMembershipFactory(
        cohort=cohort,
        learner=LearnerFactory(organisation=organisation, is_active=False),
    )
    request = _cohort_table_request(site_aware_request, organisation, "")

    (row,) = CohortDataTable.get_queryset(request)

    assert row.learner_count == 1


@pytest.mark.django_db
def test_cohort_list_courses_cell_omits_an_inactive_registration(staff_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Live Course")
    )
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Dropped Course"), is_active=False
    )

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (row,) = document.xpath(f"//tr[contains(., '{cohort.name}')]")
    assert "Live Course" in row.text_content()
    assert "Dropped Course" not in row.text_content()


@pytest.mark.django_db
def test_cohort_list_omits_an_inactive_cohort_by_default(staff_client):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Running group")
    CohortFactory(organisation=organisation, name="Retired group", is_active=False)

    text = staff_client.get(
        _interface_url(organisation.slug, "cohorts")
    ).content.decode()

    assert "Running group" in text
    assert "Retired group" not in text


@pytest.mark.django_db
def test_cohort_list_show_inactive_chip_reads_the_label_once(staff_client):
    """The applied toggle chip used to read "Show inactive: Show inactive"."""
    organisation = OrganisationFactory()

    response = staff_client.get(
        _interface_url(organisation.slug, "cohorts") + "?cohorts-inactive=1"
    )

    document = lxml.html.fromstring(response.content.decode())
    remove_links = document.xpath("//a[@aria-label='Remove Show inactive filter']")
    chip_texts = {
        " ".join(link.getparent().text_content().split()) for link in remove_links
    }
    assert chip_texts == {"Show inactive"}


@pytest.mark.django_db
def test_cohort_list_includes_an_inactive_cohort_with_a_badge_when_asked(
    staff_client,
):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Retired group", is_active=False)

    response = staff_client.get(
        _interface_url(organisation.slug, "cohorts") + "?cohorts-inactive=1"
    )

    document = lxml.html.fromstring(response.content.decode())
    (row,) = document.xpath("//tr[contains(., 'Retired group')]")
    assert "Inactive" in row.text_content()


@pytest.mark.django_db
def test_cohort_list_course_filter_keeps_cohorts_with_an_active_registration(
    site_aware_request,
):
    organisation = OrganisationFactory()
    course = CourseFactory()
    holding = CohortFactory(organisation=organisation, name="Holding")
    CohortFactory(organisation=organisation, name="Empty")
    lapsed = CohortFactory(organisation=organisation, name="Lapsed")
    CohortCourseRegistrationFactory(cohort=holding, course=course)
    CohortCourseRegistrationFactory(cohort=lapsed, course=course, is_active=False)

    names = _cohort_names(
        site_aware_request, organisation, f"cohorts-course={course.pk}"
    )

    assert names == ["Holding"]


class TestCohortListQueryCount:
    def _query_count(
        self, site_aware_request, cohort_count: int, query_string: str
    ) -> int:
        organisation = OrganisationFactory()
        course = CourseFactory()
        for _ in range(cohort_count):
            cohort = CohortFactory(organisation=organisation)
            CohortMembershipFactory(cohort=cohort)
            CohortCourseRegistrationFactory(cohort=cohort, course=course)
        request = _cohort_table_request(
            site_aware_request,
            organisation,
            query_string.format(course=course.pk),
        )
        query = CohortDataTable.parse_query(request, "cohorts")
        queryset = CohortDataTable.filter_queryset(
            request, CohortDataTable.get_queryset(request), query
        )
        with CaptureQueriesContext(connection) as captured:
            render_to_string(
                "panel_framework/panels/data_table_region.html",
                CohortDataTable.get_context(
                    request,
                    query,
                    queryset,
                    base_url="",
                    page_url="",
                    region_id="t",
                ),
                request=request,
            )
        return len(captured.captured_queries)

    @pytest.mark.django_db
    def test_query_count_does_not_grow_with_cohort_count(self, site_aware_request):
        one = self._query_count(site_aware_request, 1, "")
        ten = self._query_count(site_aware_request, 10, "")

        assert one == ten

    @pytest.mark.django_db
    def test_query_count_with_the_course_filter_does_not_grow_with_cohort_count(
        self, site_aware_request
    ):
        one = self._query_count(site_aware_request, 1, "cohorts-course={course}")
        ten = self._query_count(site_aware_request, 10, "cohorts-course={course}")

        assert one == ten


def _cohort_page(client: Client, cohort: Cohort) -> lxml.html.HtmlElement:
    return _get_document(
        client, _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}")
    )


def _add_member(cohort: Cohort) -> Learner:
    learner = cast(Learner, LearnerFactory(organisation=cohort.organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner


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
        b.get("hx-get") for b in document.cssselect("section[data-panel] footer button")
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


@pytest.mark.django_db
def test_cohort_list_learners_cell_reads_zero_for_a_cohort_with_no_active_learners(
    staff_client,
):
    """The Learners cell showed the empty-value dash instead of 0."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Empty group")
    CohortMembershipFactory(
        cohort=cohort,
        learner=LearnerFactory(organisation=organisation, is_active=False),
    )

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (row,) = document.xpath("//tr[contains(., 'Empty group')]")
    cells = [" ".join(td.text_content().split()) for td in row.xpath("./td")]
    assert "0" in cells


def _learner_page(
    client: Client, learner: Learner, tab: str = ""
) -> lxml.html.HtmlElement:
    path = f"learners/{learner.pk}" + (f"/__tabs/{tab}" if tab else "")
    return _get_document(client, _interface_url(learner.organisation.slug, path))


def _region_text(document: lxml.html.HtmlElement) -> str:
    (region,) = document.cssselect("[data-tab-set]")
    return str(region.text_content())


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
def test_the_cohorts_list_shows_created_as_day_month_year_and_24_hour_time(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    Cohort.objects.filter(pk=cohort.pk).update(
        created_at=datetime(2026, 11, 3, 7, 37, tzinfo=UTC)
    )

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (region,) = document.cssselect("[data-table-region]")
    assert "3 Nov 2026, 07:37" in " ".join(region.text_content().split())


@pytest.mark.django_db
def test_the_learner_overview_details_card_lists_name_email_status_and_date_added(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())

    document = _learner_page(staff_client, learner, "overview")

    labels = [dt.text_content().strip() for dt in document.cssselect("dl dt")]
    assert labels == ["Name", "Email", "Status", "Date added"]


@pytest.mark.django_db
def test_the_learner_cohorts_card_shows_the_join_date(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    membership = CohortMembershipFactory(
        learner=learner, cohort=CohortFactory(organisation=organisation)
    )
    CohortMembership.objects.filter(pk=membership.pk).update(
        created_at=datetime(2024, 3, 5, tzinfo=UTC)
    )

    document = _learner_page(staff_client, learner, "overview")

    (table,) = document.cssselect("#cohorts-table")
    assert "5 Mar 2024, 00:00" in " ".join(table.text_content().split())


@pytest.mark.django_db
def test_the_registrations_card_names_an_individual_registration_individual(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "Individual" in row.text_content()


@pytest.mark.django_db
def test_the_registrations_card_names_the_cohort_of_a_cohort_registration(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    CohortMembershipFactory(learner=learner, cohort=cohort)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "via Evening group" in row.text_content()


@pytest.mark.django_db
def test_the_registrations_list_shows_no_list_markers(staff_client: Client):
    """The theme bullets and indents bare lists, so the card's rows sat 24px in."""
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "list-none" in row.getparent().get("class").split()


@pytest.mark.django_db
def test_the_registrations_card_shows_an_inactive_individual_registration_inactive(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra"), is_active=False
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "Inactive" in row.text_content()


@pytest.mark.django_db
def test_the_registrations_card_leaves_out_a_course_from_an_inactive_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, is_active=False)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    assert not document.cssselect("[data-testid='registration-row']")


@pytest.mark.django_db
def test_the_courses_tab_shows_the_recomputed_percentage_not_the_stored_one(
    staff_client: Client,
):
    course = CourseFactory(title="Algebra")
    done_topic = TopicFactory()
    open_topic = TopicFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=done_topic, order=0
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=open_topic, order=1
    )
    record = course_progress_record(course, UserFactory(), progress_percentage=90)
    topic_progress(record, done_topic, complete_time=timezone.now())

    document = _learner_page(staff_client, record.learner, "courses")

    text = _region_text(document)
    assert "50%" in text
    assert "90%" not in text


@pytest.mark.django_db
def test_the_courses_tab_says_nothing_completed_for_a_registration_without_activity(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "courses")

    assert "Nothing completed yet" in _region_text(document)


@pytest.mark.django_db
def test_the_history_tab_renders_its_empty_state(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())

    response = staff_client.get(
        _interface_url(
            learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
        )
    )

    template_names = [t.name for t in response.templates]
    assert "panel_framework/partials/table_empty.html" in template_names


def _history_entry(learner: Learner, **overrides: object) -> AuditLogEntry:
    return cast(
        AuditLogEntry,
        AuditLogEntryFactory(
            target=learner,
            organisation=learner.organisation,
            action="learner.deactivated",
            **overrides,
        ),
    )


def _visible_text(element: lxml.html.HtmlElement) -> str:
    """The text of `element` without the avatar chip's inline stylesheet."""
    clone = copy.deepcopy(element)
    for style in clone.cssselect("style"):
        style.drop_tree()
    return str(clone.text_content()).strip()


def _entry_rows(document: lxml.html.HtmlElement, selector: str) -> list[list[str]]:
    """Each entry row's data cells, without its toggle cell or its detail row."""
    return [
        [_visible_text(cell) for cell in row.cssselect("td")][1:]
        for row in document.cssselect(f"{selector} tbody tr:not([data-row-detail])")
    ]


def _row_details(document: lxml.html.HtmlElement, selector: str) -> list[str]:
    """The text of each row detail, in row order."""
    return [
        " ".join(row.text_content().split())
        for row in document.cssselect(f"{selector} tbody tr[data-row-detail]")
    ]


def _history_rows(document: lxml.html.HtmlElement) -> list[list[str]]:
    return _entry_rows(document, "[data-tab-set]")


@pytest.mark.django_db
def test_the_history_tab_lists_entries_naming_the_learner_only(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    other = LearnerFactory(organisation=organisation)
    _history_entry(learner, actor_label="Ada Admin")
    _history_entry(other, actor_label="Someone Else")

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [(row[1], row[2]) for row in rows] == [("Ada Admin", "Learner deactivated")]


@pytest.mark.django_db
def test_the_history_tab_lists_the_newest_entry_first(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    now = timezone.now()
    _history_entry(learner, reason="older", created_at=now - timedelta(hours=1))
    _history_entry(learner, reason="newer", created_at=now)

    document = _learner_page(staff_client, learner, "history")

    assert _row_details(document, "[data-tab-set]") == ["Reason newer", "Reason older"]


@pytest.mark.django_db
def test_the_history_tab_pages_stably_when_entries_share_a_timestamp(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    when = timezone.now()
    for number in range(26):
        _history_entry(learner, reason=f"entry {number}", created_at=when)

    first_document = _learner_page(staff_client, learner, "history")
    second_page = staff_client.get(
        _interface_url(
            learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
        ),
        {"history-page": 2},
    )
    second_document = lxml.html.fromstring(second_page.content.decode())

    first = _row_details(first_document, "[data-tab-set]")
    second = _row_details(second_document, "[data-tab-set]")
    assert (len(first), len(second), len(set(first + second))) == (25, 1, 26)


@pytest.mark.django_db
def test_the_history_tab_names_the_system_when_there_is_no_actor(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, actor_label="")

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert rows[0][1] == "System"


@pytest.mark.django_db
def test_the_history_tab_escapes_user_derived_text(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, actor_label="<b>actor</b>", reason="<b>why</b>")

    response = staff_client.get(
        _interface_url(
            learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
        )
    )

    content = response.content.decode()
    assert "&lt;b&gt;actor&lt;/b&gt;" in content
    assert "&lt;b&gt;why&lt;/b&gt;" in content
    assert "<b>actor</b>" not in content


@pytest.mark.django_db
def test_a_history_row_has_three_cells_and_a_toggle_with_the_reason_in_its_detail(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, reason="Asked to leave")

    document = _learner_page(staff_client, learner, "history")

    (row,) = document.cssselect("[data-tab-set] tbody tr:not([data-row-detail])")
    (detail,) = document.cssselect("[data-tab-set] tbody tr[data-row-detail]")
    toggle = row.cssselect("td button[aria-expanded]")
    cells = [cell.text_content().strip() for cell in row.cssselect("td")]
    assert (
        len(cells),
        cells[3],
        len(toggle),
        toggle[0].get("aria-controls"),
        detail.get("id"),
        "Asked to leave" in detail.text_content(),
        "Asked to leave" in row.text_content(),
    ) == (
        4,
        "Learner deactivated",
        1,
        detail.get("id"),
        detail.get("id"),
        True,
        False,
    )


@pytest.mark.django_db
def test_an_entry_with_no_description_reason_or_run_entries_has_no_toggle(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, reason="")

    document = _learner_page(staff_client, learner, "history")

    assert (
        document.cssselect("[data-tab-set] tbody button[aria-expanded]"),
        document.cssselect("[data-tab-set] tbody tr[data-row-detail]"),
    ) == ([], [])


@pytest.mark.django_db
def test_the_when_cell_has_an_iso_datetime_and_reads_as_one_run_of_date_then_time(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, created_at=datetime(2026, 3, 4, 10, 14, tzinfo=UTC))

    document = _learner_page(staff_client, learner, "history")

    (time_element,) = document.cssselect("[data-tab-set] tbody time")
    stamp = datetime.fromisoformat(time_element.get("datetime"))
    assert (
        stamp.utcoffset() is not None,
        stamp == datetime(2026, 3, 4, 10, 14, tzinfo=UTC),
        " ".join(time_element.text_content().split()).startswith("4 Mar 2026, "),
        # The date and the time share a colour.
        time_element.cssselect(".text-muted"),
    ) == (True, True, True, [])


@pytest.mark.django_db
def test_the_history_tab_shows_the_code_of_a_deactivated_action(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=learner, organisation=learner.organisation, action="widget.exploded"
    )

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert rows[0][2] == "widget.exploded"


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
def test_a_cohort_admin_gets_no_history_tab_and_a_404_on_its_url(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    client = logged_in_client(educator)

    document = _get_document(
        client, _interface_url(organisation.slug, f"learners/{learner.pk}")
    )
    response = client.get(
        _interface_url(organisation.slug, f"learners/{learner.pk}/__tabs/history")
    )

    (nav,) = document.cssselect("nav[aria-label='Learner sections']")
    hrefs = [a.get("href").rsplit("/", 1)[-1] for a in nav.cssselect("a")]
    assert ("history" in hrefs, response.status_code) == (False, 404)


@pytest.mark.django_db
def test_an_admin_of_another_organisation_gets_a_404_on_the_history_tab(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    other_organisation = OrganisationFactory()
    grantor = LearnerFactory(user__superuser=True).user
    admin = LearnerFactory(user__staff=True, organisation=other_organisation).user
    assign_role(grantor, admin, "organisation_admin", other_organisation)

    response = logged_in_client(admin).get(
        _interface_url(organisation.slug, f"learners/{learner.pk}/__tabs/history")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_history_tab_renders_within_a_query_budget(
    staff_client: Client, django_assert_max_num_queries
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    for number in range(25):
        _history_entry(learner, reason=f"entry {number}")
    url = _interface_url(
        learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
    )

    with django_assert_max_num_queries(QUERY_BUDGET):
        staff_client.get(url)


def _history_export_url(learner: Learner) -> str:
    return _interface_url(
        learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
    )


def _export_audit_csv(
    client: Client, url: str, table_key: str = "history"
) -> tuple[list[str], list[list[str]], str]:
    """An audit table's CSV export at ``url``: (header, rows, Content-Disposition)."""
    response = client.get(url, {f"{table_key}-export": "csv"})
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    header, *rows = list(csv.reader(io.StringIO(body, newline="")))
    return header, rows, response["Content-Disposition"]


@pytest.mark.django_db
def test_the_learner_history_export_holds_every_entry_naming_the_learner(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    other = LearnerFactory(organisation=organisation)
    for number in range(30):
        _history_entry(learner, reason=f"reason {number}")
    _history_entry(other, reason="not ours")

    header, rows, _disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert header == [
        "When",
        "Who",
        "Actor email",
        "What",
        "Action",
        "Target",
        "Description",
        "Reason",
        "Run ID",
    ]
    assert (len(rows), "not ours" in {row[7] for row in rows}) == (30, False)


@pytest.mark.django_db
def test_the_learner_history_export_is_named_for_the_learner(staff_client: Client):
    learner = LearnerFactory(
        organisation=OrganisationFactory(),
        user__first_name="Ada",
        user__last_name="Able",
    )
    _history_entry(learner)

    _header, _rows, disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert disposition == (
        f'attachment; filename="history-ada-able-{timezone.localdate():%Y-%m-%d}.csv"'
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_a_cohort_role_gets_a_404_on_the_learner_history_export(
    mock_site_context, logged_in_client, role: str
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, role, cohort)

    response = logged_in_client(educator).get(
        _history_export_url(learner), {"history-export": "csv"}
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_learner_history_export_neutralises_a_formula_and_keeps_unicode(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, reason="=1+1", target_label="Zoë Ångström")

    _header, (row,), _disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert (row[7], row[5]) == ("'=1+1", "Zoë Ångström")


@pytest.mark.django_db
def test_the_learner_history_export_leaves_actor_email_empty_for_a_system_entry(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, actor=None, actor_label="")

    _header, (row,), _disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert (row[1], row[2]) == ("System", "")


@pytest.mark.django_db
def test_the_learner_history_export_leaves_actor_email_empty_for_a_deleted_actor(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    actor = UserFactory(email="gone@example.com")
    _history_entry(learner, actor=actor, actor_label="Gone Person")
    actor.delete()

    _header, (row,), _disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert (row[1], row[2]) == ("Gone Person", "")


@pytest.mark.django_db
def test_the_learner_history_toolbar_offers_the_csv_export(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner)

    document = _learner_page(staff_client, learner, "history")

    links = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert links
    assert all("history-export=csv" in a.get("href") for a in links)


@pytest.mark.django_db
def test_the_learner_history_export_records_one_entry_for_the_organisation(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Able"
    )
    for _ in range(3):
        _history_entry(learner)

    _export_audit_csv(staff_client, _history_export_url(learner))

    entry = AuditLogEntry.objects.get(action="audit_log.exported")
    assert (
        entry.actor_id,
        entry.target_object_id,
        entry.details,
    ) == (
        User.objects.get(is_superuser=True).pk,
        str(organisation.pk),
        {"scope": "learner", "scope_label": "Ada Able", "count": 3, "filters": ""},
    )


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
def test_the_learner_history_export_omits_its_own_entry_and_a_second_export_adds_another(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner)
    url = _history_export_url(learner)

    _header, first_rows, _disposition = _export_audit_csv(staff_client, url)
    _header, second_rows, _disposition = _export_audit_csv(staff_client, url)

    assert (
        len(first_rows),
        len(second_rows),
        AuditLogEntry.objects.filter(action="audit_log.exported").count(),
    ) == (1, 1, 2)


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
def test_a_cohort_rows_remove_and_move_triggers_name_the_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    CohortMembershipFactory(learner=learner, cohort=cohort)

    document = _learner_page(staff_client, learner, "overview")

    labels = {
        button.get("aria-label")
        for button in document.cssselect("button[hx-get]")
        if f"?cohort={cohort.pk}" in button.get("hx-get")
    }
    assert labels == {"Remove from Evening group", "Move from Evening group"}


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


@pytest.fixture
def role_holder_client(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> Callable[[Organisation | Cohort, str], Client]:
    """Factory: a logged-in staff user holding `role` on `target`."""

    def _make(
        target: Organisation | Cohort, role: str = "organisation_admin"
    ) -> Client:
        user = UserFactory(staff=True)
        assign_role(UserFactory(superuser=True), user, role, target)
        return logged_in_client(user)

    return _make


def _grant_staff_member(
    target: Organisation | Cohort, role: str = "organisation_admin", **user_fields: str
) -> None:
    assign_role(UserFactory(superuser=True), UserFactory(**user_fields), role, target)


@pytest.mark.django_db
def test_an_organisation_admin_sees_each_members_name_and_email(role_holder_client):
    organisation = OrganisationFactory()
    _grant_staff_member(
        organisation, first_name="Ada", last_name="Lovelace", email="ada@example.com"
    )
    client = role_holder_client(organisation, "organisation_admin")

    text = _get_document(client, _interface_url(organisation.slug, "staff"))

    assert "Ada Lovelace" in text.text_content()
    assert "ada@example.com" in text.text_content()


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
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_members_is_a_404_for_a_cohort_role_holder(role_holder_client, role):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, role)

    response = client.get(_interface_url(organisation.slug, "staff"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_site_admin_with_no_role_in_the_organisation_can_open_members(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", mock_site_context
    )

    response = logged_in_client(site_admin).get(
        _interface_url(organisation.slug, "staff")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_nameless_member_shows_the_email_alone(role_holder_client):
    organisation = OrganisationFactory()
    _grant_staff_member(
        organisation, first_name="", last_name="", email="bare@example.com"
    )
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(client, _interface_url(organisation.slug, "staff"))

    names = [
        e.text_content() for e in document.cssselect("#main-content span.truncate")
    ]
    assert "bare@example.com" in names
    assert not document.cssselect("#main-content span.truncate.text-muted")


@pytest.mark.django_db
def test_a_member_path_with_an_id_under_it_is_a_404(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    response = client.get(_interface_url(organisation.slug, f"staff/{uuid.uuid4()}"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_member_name_is_escaped(role_holder_client):
    organisation = OrganisationFactory()
    _grant_staff_member(organisation, first_name="<b>x</b>")
    client = role_holder_client(organisation, "organisation_admin")

    response = client.get(_interface_url(organisation.slug, "staff"))

    assert "&lt;b&gt;x&lt;/b&gt;" in response.content.decode()
    assert "<b>x</b>" not in response.content.decode()


def _staff_document(client: Client, organisation: Organisation):
    return _get_document(client, _interface_url(organisation.slug, "staff"))


def _staff_member_row(document, email: str):
    """The table row whose text includes `email`."""
    (row,) = [
        r
        for r in document.cssselect("#main-content tbody tr")
        if email in r.text_content()
    ]
    return row


def _scope_lines(row) -> list[str]:
    return [e.text_content().strip() for e in row.cssselect("ul li span[title]")]


# Measured for a page of ten: the count must not grow with the number of rows.
QUERY_BOUND = 66


MARKERS = {"You", "Inactive", "Account inactive", "Also a learner"}


def _marker_labels(row) -> set[str]:
    return {e.text_content().strip() for e in row.cssselect("span")} & MARKERS


def _hold(user, role: str, target, grantor=None) -> None:
    assign_role(grantor or UserFactory(superuser=True), user, role, target)


@pytest.mark.django_db
def test_an_organisation_admins_roles_cell_reads_whole_organisation(role_holder_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="boss@example.com"), "organisation_admin", organisation)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "boss@example.com")

    assert _scope_lines(row) == ["Whole organisation"]
    assert "Organisation admin" in row.text_content()


@pytest.mark.django_db
def test_two_cohorts_read_both_names(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="two@example.com")
    for name in ("Alpha", "Bravo"):
        _hold(user, "cohort_admin", CohortFactory(organisation=organisation, name=name))
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "two@example.com")

    assert _scope_lines(row) == ["Alpha, Bravo"]


@pytest.mark.django_db
def test_four_cohorts_read_two_names_and_the_rest_as_a_count(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="four@example.com")
    for name in ("Alpha", "Bravo", "Charlie", "Delta"):
        _hold(
            user, "cohort_viewer", CohortFactory(organisation=organisation, name=name)
        )
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "four@example.com")

    (scope,) = row.cssselect("ul li span[title]")
    assert scope.text_content().strip() == "Alpha, Bravo +2 more"
    assert scope.get("title") == "Alpha, Bravo, Charlie, Delta"


@pytest.mark.django_db
def test_an_inactive_cohort_carries_the_inactive_marker(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Old", is_active=False)
    _hold(UserFactory(email="old@example.com"), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "old@example.com")

    assert _scope_lines(row) == ["Old (inactive)"]


def _staff_quick_view_text(client: Client, organisation, email: str) -> str:
    user = User.objects.get(email=email)
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"staff/{user.pk}/__quick-view",
            },
        ),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    body = lxml.html.fromstring(response.content.decode())
    return " ".join(body.text_content().split())


@pytest.mark.django_db
def test_a_role_names_who_added_it(role_holder_client):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True, first_name="Grace", last_name="Hopper")
    _hold(
        UserFactory(email="added@example.com"),
        "organisation_admin",
        organisation,
        grantor,
    )
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "added@example.com")
    quick_view = _staff_quick_view_text(client, organisation, "added@example.com")

    assert "by Grace Hopper" not in row.text_content()
    assert "by Grace Hopper" in quick_view


@pytest.mark.django_db
def test_a_role_with_no_recorded_grantor_reads_added_without_a_by_clause(
    role_holder_client,
):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True)
    _hold(
        UserFactory(email="orphan@example.com"),
        "organisation_admin",
        organisation,
        grantor,
    )
    grantor.delete()
    client = role_holder_client(organisation, "organisation_admin")

    text = _staff_quick_view_text(client, organisation, "orphan@example.com")

    assert "Added" in text
    assert " by " not in text
    assert "Not recorded" not in text


def _make_viewer_and_subject(role_holder_client, organisation, case: str):
    """Returns (client, email of the row to inspect) for a marker case."""
    subject = UserFactory(email="subject@example.com")
    _hold(subject, "cohort_viewer", CohortFactory(organisation=organisation))
    viewer_client = role_holder_client(organisation, "organisation_admin")
    if case == "membership_inactive":
        StaffMember.objects.filter(user=subject).update(is_active=False)
    elif case == "account_inactive":
        subject.is_active = False
        subject.save()
    elif case == "learner":
        LearnerFactory(user=subject, organisation=organisation)
    elif case == "inactive_learner":
        LearnerFactory(user=subject, organisation=organisation, is_active=False)
    return viewer_client


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("plain", set()),
        ("membership_inactive", {"Inactive"}),
        ("account_inactive", {"Account inactive"}),
        ("learner", {"Also a learner"}),
        ("inactive_learner", set()),
    ],
)
def test_each_marker_appears_for_its_case_only(role_holder_client, case, expected):
    organisation = OrganisationFactory()
    client = _make_viewer_and_subject(role_holder_client, organisation, case)

    row = _staff_member_row(
        _staff_document(client, organisation), "subject@example.com"
    )

    assert _marker_labels(row) == expected


@pytest.mark.django_db
def test_the_inactive_marker_is_muted(role_holder_client):
    organisation = OrganisationFactory()
    client = _make_viewer_and_subject(
        role_holder_client, organisation, "membership_inactive"
    )

    row = _staff_member_row(
        _staff_document(client, organisation), "subject@example.com"
    )

    (marker,) = [
        e
        for e in row.cssselect("[data-tone]")
        if e.text_content().strip() == "Inactive"
    ]
    assert marker.get("data-tone") == "muted"


@pytest.mark.django_db
def test_the_viewers_own_row_is_marked_you(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")
    document = _staff_document(client, organisation)

    (row,) = document.cssselect("#main-content tbody tr")

    assert _marker_labels(row) == {"You"}


VIEWER_ROLE_SECTIONS = [
    "dashboard",
    "learners",
    "cohorts",
    "courses",
    "audit-log",
]


@pytest.mark.django_db
def test_a_staff_viewer_sees_names_and_no_roles_or_buttons(role_holder_client):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(email="subject@example.com", first_name="Sam", last_name="Subject"),
        "organisation_admin",
        organisation,
    )
    client = role_holder_client(organisation, "organisation_staff_viewer")

    response = client.get(_interface_url(organisation.slug, "staff"))
    document = lxml.html.fromstring(response.content)

    assert response.status_code == 200
    assert "Sam Subject" in document.text_content()
    assert (
        "Organisation admin"
        not in document.cssselect("#main-content tbody")[0].text_content()
    )
    assert document.cssselect("#main-content tbody button[hx-get]") == []


@pytest.mark.django_db
@pytest.mark.parametrize("section", VIEWER_ROLE_SECTIONS)
@pytest.mark.parametrize(
    "role", ["organisation_staff_viewer", "organisation_staff_roles_viewer"]
)
def test_a_staff_viewer_role_gets_404_outside_the_staff_section(
    role_holder_client, role, section
):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, role)

    response = client.get(_interface_url(organisation.slug, section))

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_sidebar_of_a_staff_viewer_lists_staff_alone(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_staff_viewer")

    document = _staff_document(client, organisation)

    (nav,) = document.cssselect("#sidebar-nav")
    assert [a.text_content().strip() for a in nav.cssselect("a")] == ["Staff"]


@pytest.mark.django_db
def test_the_staff_page_lists_only_the_roles_the_site_defines(
    mock_site_context: Site, settings: SettingsWrapper, role_holder_client
):
    organisation = OrganisationFactory()
    without = frozenset(
        {"organisation_staff_viewer", "organisation_staff_roles_viewer"}
    )
    with custom_role_config(mock_site_context, settings, without=without):
        client = role_holder_client(organisation, "organisation_admin")

        document = _staff_document(client, organisation)

    (role_filter,) = document.cssselect("select[name=staff-role]")
    assert [option.get("value") for option in role_filter.cssselect("option")] == [
        "all",
        "organisation_admin",
        "cohort_admin",
        "cohort_viewer",
    ]


@pytest.mark.django_db
def test_a_roles_viewer_sees_role_names_and_no_buttons(role_holder_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="subject@example.com"), "organisation_admin", organisation)
    client = role_holder_client(organisation, "organisation_staff_roles_viewer")

    document = _staff_document(client, organisation)
    row = _staff_member_row(document, "subject@example.com")

    assert "Organisation admin" in row.text_content()
    assert row.cssselect("button[hx-get]") == []


@pytest.mark.django_db
def test_a_cohort_admin_still_sees_the_dashboard(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, "cohort_admin")

    response = client.get(_interface_url(organisation.slug, ""))

    assert response.status_code == 302
    assert response["Location"] == _interface_url(organisation.slug, "dashboard")


@pytest.mark.django_db
def test_a_staff_member_with_no_staff_member_row_is_inactive(role_holder_client):
    organisation = OrganisationFactory()
    subject = UserFactory(email="subject@example.com")
    _hold(subject, "organisation_admin", organisation)
    StaffMember.objects.filter(user=subject).delete()
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(
        _staff_document(client, organisation), "subject@example.com"
    )

    assert _marker_labels(row) == {"Inactive"}


@pytest.mark.django_db
def test_a_superuser_holding_one_cohort_role_shows_that_role_only(role_holder_client):
    organisation = OrganisationFactory()
    superuser = UserFactory(superuser=True, email="super@example.com")
    _hold(superuser, "cohort_viewer", CohortFactory(organisation=organisation))
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "super@example.com")

    roles = row.cssselect("ul")[0]
    assert len(roles.cssselect("li")) == 1
    assert "Cohort viewer" in roles.text_content()


@pytest.mark.django_db
def test_a_cohort_name_is_escaped_in_the_scope(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="<i>x</i>")
    _hold(UserFactory(), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    content = client.get(_interface_url(organisation.slug, "staff")).content.decode()

    assert "&lt;i&gt;x&lt;/i&gt;" in content
    assert "<i>x</i>" not in content


@pytest.mark.django_db
def test_a_full_page_of_members_stays_within_a_fixed_query_bound(
    role_holder_client, django_assert_max_num_queries
):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True)
    for _ in range(10):
        user = UserFactory()
        _hold(user, "organisation_admin", organisation, grantor)
        _hold(user, "cohort_viewer", CohortFactory(organisation=organisation), grantor)
        LearnerFactory(user=user, organisation=organisation)
    client = role_holder_client(organisation, "organisation_admin")
    url = _interface_url(organisation.slug, "staff")

    with django_assert_max_num_queries(QUERY_BOUND):
        response = client.get(url)

    assert response.status_code == 200
    assert (
        len(
            lxml.html.fromstring(response.content.decode()).cssselect(
                "#main-content tbody tr"
            )
        )
        == 10
    )


def _member_emails(document) -> list[str]:
    return [
        row.cssselect("td")[0].text_content()
        for row in document.cssselect("#main-content tbody tr")
    ]


def _members_search(client: Client, organisation: Organisation, term: str):
    return _get_document(
        client, _interface_url(organisation.slug, "staff") + f"?staff-q={term}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "term", ["Wanjiru", "Kamau", "wanjiru.k@"], ids=["first", "last", "email"]
)
def test_members_search_matches_first_name_last_name_and_email(
    role_holder_client, term
):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(first_name="Wanjiru", last_name="Kamau", email="wanjiru.k@x.org"),
        "organisation_admin",
        organisation,
    )
    _hold(UserFactory(email="other@x.org"), "organisation_admin", organisation)
    client = role_holder_client(organisation, "organisation_admin")

    document = _members_search(client, organisation, term)

    (row,) = document.cssselect("#main-content tbody tr")
    assert "wanjiru.k@x.org" in row.text_content()


@pytest.mark.django_db
def test_the_role_filter_narrows_the_members_page(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    _hold(UserFactory(email="viewer@x.org"), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(
        client,
        _interface_url(organisation.slug, "staff") + "?staff-role=cohort_viewer",
    )

    (row,) = document.cssselect("#main-content tbody tr")
    assert "viewer@x.org" in row.text_content()


@pytest.mark.django_db
def test_picking_a_role_from_the_default_drops_all_roles_from_its_link(
    role_holder_client,
):
    """From the default "All roles" state, a role's choice link selected only
    that role instead of keeping "All roles" beside it."""
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _staff_document(client, organisation)

    (link,) = [
        a
        for a in document.cssselect("details a")
        if a.text_content().strip() == "Cohort admin"
    ]
    assert link.get("href").endswith("?staff-role=cohort_admin")


@pytest.mark.django_db
def test_the_mobile_role_select_has_a_single_all_roles_option(role_holder_client):
    """The mobile Role select listed both a blank "All" and "All roles"."""
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _staff_document(client, organisation)

    (select,) = document.cssselect("select[name=staff-role]")
    labels = [o.text_content().strip() for o in select.cssselect("option")]
    assert labels[:2] == ["All roles", "Organisation admin"]


ONLY_STAFF_MEMBER_LINE = "You're the only staff member here."


@pytest.mark.django_db
def test_a_lone_organisation_admin_is_told_they_are_the_only_member(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    text = _staff_document(client, organisation).text_content()

    assert ONLY_STAFF_MEMBER_LINE in text


@pytest.mark.django_db
def test_the_only_member_line_goes_once_a_second_member_exists(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")
    _hold(UserFactory(), "organisation_admin", organisation)

    text = _staff_document(client, organisation).text_content()

    assert ONLY_STAFF_MEMBER_LINE not in text


@pytest.mark.django_db
def test_the_member_header_first_links_to_descending_first_name(role_holder_client):
    """The list already arrives by first name, so the first click flips it."""
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(client, _interface_url(organisation.slug, "staff"))

    (link,) = document.xpath("//thead//a[normalize-space()='Staff member']")
    assert "staff-sort=-first_name" in link.get("href")


@pytest.mark.django_db
def test_a_search_with_no_match_says_so_and_offers_to_clear_filters(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _members_search(client, organisation, "nobody-has-this-name")

    (cell,) = document.cssselect("#main-content tbody td")
    (link,) = cell.cssselect("a")
    assert (
        cell.text_content().split("Clear filters")[0].strip()
        == "No staff members match these filters."
    )
    assert "staff-q" not in link.get("href")


@pytest.mark.django_db
def test_a_filter_with_no_match_says_so(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    document = _get_document(
        client,
        _interface_url(organisation.slug, "staff") + "?staff-role=cohort_viewer",
    )

    (cell,) = document.cssselect("#main-content tbody td")
    assert "No staff members match these filters." in cell.text_content()


@pytest.mark.django_db
def test_an_organisation_with_no_members_says_so(mock_site_context, logged_in_client):
    organisation = OrganisationFactory()
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", mock_site_context
    )

    document = _staff_document(logged_in_client(site_admin), organisation)

    (cell,) = document.cssselect("#main-content tbody td")
    assert "No staff yet." in cell.text_content()
    assert "Add staff member" in cell.text_content()


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


@pytest.mark.django_db
def test_an_organisation_admins_own_row_offers_role_triggers_but_no_state_trigger(
    role_holder_client,
):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True, email="me@example.com")
    assign_role(UserFactory(superuser=True), viewer, "organisation_admin", organisation)
    client = Client()
    client.force_login(viewer)

    row = _staff_member_row(_staff_document(client, organisation), "me@example.com")

    urls = [button.get("hx-get") for button in row.cssselect("button[hx-get]")]
    assert any("add_role" in url for url in urls)
    assert any("deactivate_role" in url for url in urls)
    assert not any(
        url.split("?")[0].endswith(("/deactivate", "/reactivate")) for url in urls
    )
    assert not row.cssselect("[aria-label='Locked']")


def _remove_triggers(row) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if "deactivate_role" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_a_cohort_admins_own_row_offers_the_roles_they_may_give(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    viewer = UserFactory(staff=True, email="me@example.com")
    superuser = UserFactory(superuser=True)
    assign_role(superuser, viewer, "cohort_admin", cohort)
    assign_role(superuser, viewer, "organisation_staff_roles_viewer", organisation)
    client = Client()
    client.force_login(viewer)

    row = _staff_member_row(_staff_document(client, organisation), "me@example.com")

    labels = {b.text_content().strip() for b in row.cssselect("button[hx-get]")}
    assert {"Add role", "Deactivate role"} <= labels
    assert "Deactivate staff member" not in labels
    assert "You can't change your own roles" not in row.text_content()


@pytest.mark.django_db
def test_another_members_entry_offers_remove_to_an_organisation_admin(
    role_holder_client,
):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    cohort = CohortFactory(organisation=organisation)
    _hold(user, "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    (trigger,) = _remove_triggers(row)
    assert f"user={user.pk}&role=cohort_viewer" in trigger


def _change_cohorts_triggers(row) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if "change_cohorts" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_a_cohort_role_entry_offers_change_cohorts(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    (trigger,) = _change_cohorts_triggers(row)
    assert f"user={user.pk}&role=cohort_viewer" in trigger


@pytest.mark.django_db
def test_an_organisation_admin_entry_offers_no_change_cohorts(role_holder_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="boss@example.com"), "organisation_admin", organisation)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "boss@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_a_viewer_role_entry_offers_no_change_cohorts(role_holder_client):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(email="watcher@example.com"),
        "organisation_staff_roles_viewer",
        organisation,
    )
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(
        _staff_document(client, organisation), "watcher@example.com"
    )

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_a_role_the_viewer_may_not_give_has_no_change_cohorts(
    role_holder_client, monkeypatch
):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(email="other@example.com"),
        "cohort_viewer",
        CohortFactory(organisation=organisation),
    )
    client = role_holder_client(organisation, "organisation_admin")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("organisation_admin", None)],
    )

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_a_turned_off_accounts_row_has_no_change_cohorts(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="off@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    User.objects.filter(pk=user.pk).update(is_active=False)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "off@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_an_entry_the_viewer_may_not_revoke_has_no_remove(
    role_holder_client, monkeypatch
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    _hold(UserFactory(email="other@example.com"), "cohort_viewer", cohort)
    client = role_holder_client(organisation, "organisation_admin")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("organisation_admin", None)],
    )

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    assert _remove_triggers(row) == []


@pytest.mark.django_db
def test_a_turned_off_accounts_row_offers_remove_and_nothing_else(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="off@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    User.objects.filter(pk=user.pk).update(is_active=False)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "off@example.com")

    assert len(row.cssselect("button[hx-get]")) == 1
    assert len(_remove_triggers(row)) == 1


def _state_triggers(row, action: str) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if f"__actions/{action}?" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_an_active_member_row_offers_deactivate_and_not_reactivate(role_holder_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    (trigger,) = _state_triggers(row, "deactivate")
    assert f"user={user.pk}" in trigger
    assert _state_triggers(row, "reactivate") == []


@pytest.mark.django_db
@pytest.mark.parametrize("row_state", ["inactive", "missing"])
def test_an_inactive_member_row_offers_reactivate_and_not_deactivate(
    role_holder_client, row_state
):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    members = StaffMember.objects.filter(user=user)
    if row_state == "inactive":
        members.update(is_active=False)
    else:
        members.delete()
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    (trigger,) = _state_triggers(row, "reactivate")
    assert f"user={user.pk}" in trigger
    assert _state_triggers(row, "deactivate") == []


def _make_site_level(user: User, organisation: Organisation) -> None:
    assign_role(UserFactory(superuser=True), user, "site_admin", organisation.site)


def _turn_off(user: User, organisation: Organisation) -> None:
    User.objects.filter(pk=user.pk).update(is_active=False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prepare", [_make_site_level, _turn_off], ids=["site_level", "turned_off"]
)
def test_a_site_level_or_turned_off_row_offers_neither_state_action(
    role_holder_client, prepare
):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    prepare(user, organisation)
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "other@example.com")

    assert _state_triggers(row, "deactivate") == []
    assert _state_triggers(row, "reactivate") == []


@pytest.mark.django_db
def test_the_viewers_own_row_offers_neither_state_action(role_holder_client):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True, email="me@example.com")
    assign_role(UserFactory(superuser=True), viewer, "organisation_admin", organisation)
    client = Client()
    client.force_login(viewer)

    row = _staff_member_row(_staff_document(client, organisation), "me@example.com")

    assert _state_triggers(row, "deactivate") == []
    assert _state_triggers(row, "reactivate") == []


# Shared setup for the educator's Messages tab on the learner page.


@pytest.fixture
def _messaging_on(settings) -> None:
    settings.MESSAGING_ENABLED = True


messages_section = pytest.mark.usefixtures("mock_site_context", "_messaging_on")


def _msg_educator(organisation: Organisation) -> User:
    educator = cast(User, UserFactory(staff=True))
    _grant(educator, "organisation_admin", organisation)
    return educator


def _grant(user: User, role: str, target: Organisation | Cohort | Site) -> None:
    """Give `user` a role on `target`, granted by a superuser."""
    grantor = cast(User, UserFactory(superuser=True))
    assign_role(grantor, user, role, target)


def _msg_learner(organisation: Organisation, **user_fields: str) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user=UserFactory(
                **{"first_name": "Ada", "last_name": "Lovelace"} | user_fields
            ),
        ),
    )


def _msg_conversation(user: User, other: User) -> Conversation:
    return cast(Conversation, ConversationFactory(between=(user, other)))


def _msg_url(organisation: Organisation, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
    )


@pytest.fixture
def msg_client_for(logged_in_client):
    return lambda user: cast(Client, logged_in_client(user))


@pytest.mark.django_db
def test_a_move_shows_on_the_learner_history_tab_as_from_a_to_b(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    source = CohortFactory(organisation=organisation, name="Alpha")
    destination = CohortFactory(organisation=organisation, name="Beta")
    CohortMembershipFactory(learner=learner, cohort=source)
    move_between_cohorts(learner, source, destination, actor=UserFactory())

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [row[2] for row in rows] == [
        "Learner moved between cohorts From Alpha to Beta"
    ]


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


def _card_summary(
    card: lxml.html.HtmlElement,
) -> tuple[str, list[str], list[str], bool]:
    """An audit card's title, its field labels, its Who and Target values, and
    whether its toggle names a hidden detail holding the reason."""
    (title,) = card.cssselect("p.font-bold")
    fields = card.cssselect("dl")[0]
    labels = [dt.text_content().strip() for dt in fields.cssselect("dt")]
    values = [" ".join(dd.text_content().split()) for dd in fields.cssselect("dd")]
    (toggle,) = card.cssselect("button[aria-controls]")
    (detail,) = card.cssselect("[data-row-detail]")
    return (
        title.text_content().strip(),
        labels,
        values[1:],
        toggle.get("aria-controls") == detail.get("id")
        and detail.get("hidden") is not None
        and "Asked to leave" in detail.text_content(),
    )


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


@pytest.mark.django_db
def test_the_learner_history_card_shows_the_label_then_labelled_when_and_who(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=learner,
        organisation=learner.organisation,
        action="learner.deactivated",
        actor_label="Ada Admin",
        target_label="Lee Learner",
        reason="Asked to leave",
    )

    document = _learner_page(staff_client, learner, "history")

    (card,) = document.cssselect("[data-tab-set] ul > li")
    assert _card_summary(card) == (
        "Learner deactivated",
        ["When", "Who"],
        ["Ada Admin"],
        True,
    )


@pytest.mark.django_db
def test_a_learner_registration_shows_on_the_learner_history_tab(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    register_for_course(learner, CourseFactory(title="Algebra"))

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [row[2] for row in rows] == ["Learner registered for course Algebra"]


def _audit_log_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "audit-log")


def _audit_log_rows(document: lxml.html.HtmlElement) -> list[list[str]]:
    return _entry_rows(document, "body")


@pytest.mark.django_db
def test_the_audit_log_shows_when_as_day_month_year_and_24_hour_time(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation, created_at=datetime(2026, 11, 3, 7, 37, tzinfo=UTC)
    )

    rows = _audit_log_rows(_get_document(staff_client, _audit_log_url(organisation)))

    assert " ".join(rows[0][0].split()) == "3 Nov 2026, 07:37"


@pytest.mark.django_db
def test_the_audit_log_lists_only_the_request_organisations_entries(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    other = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours", actor_label="Ada")
    AuditLogEntryFactory(target=other, target_label="Theirs", actor_label="Bob")

    rows = _audit_log_rows(_get_document(staff_client, _audit_log_url(organisation)))

    assert [row[3] for row in rows] == ["Ours"]


@pytest.mark.django_db
def test_a_site_admin_sees_each_organisations_own_entries(staff_client: Client):
    first = OrganisationFactory()
    second = OrganisationFactory()
    AuditLogEntryFactory(target=first, target_label="First entry")
    AuditLogEntryFactory(target=second, target_label="Second entry")

    first_rows = _audit_log_rows(_get_document(staff_client, _audit_log_url(first)))
    second_rows = _audit_log_rows(_get_document(staff_client, _audit_log_url(second)))

    assert ([r[3] for r in first_rows], [r[3] for r in second_rows]) == (
        ["First entry"],
        ["Second entry"],
    )


@pytest.mark.django_db
def test_an_admin_of_another_organisation_gets_a_404_on_the_audit_log(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    other_organisation = OrganisationFactory()
    grantor = LearnerFactory(user__superuser=True).user
    admin = LearnerFactory(user__staff=True, organisation=other_organisation).user
    assign_role(grantor, admin, "organisation_admin", other_organisation)

    response = logged_in_client(admin).get(_audit_log_url(organisation))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_cohort_admin_gets_a_404_on_the_audit_log_and_no_menu_entry(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    client = logged_in_client(educator)

    page = _get_document(client, _interface_url(organisation.slug, "cohorts"))
    response = client.get(_audit_log_url(organisation))
    nested = client.get(_interface_url(organisation.slug, "audit-log/anything"))

    (nav,) = page.cssselect("#sidebar-nav")
    labels = [a.text_content().strip() for a in nav.cssselect("a")]
    assert ("Audit log" in labels, response.status_code, nested.status_code) == (
        False,
        404,
        404,
    )


@pytest.mark.django_db
def test_the_audit_log_target_column_reads_the_target_label(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation,
        target_label="Spring cohort",
        actor_label="Ada Admin",
        reason="because",
    )

    document = _get_document(staff_client, _audit_log_url(organisation))

    headers = [th.text_content().strip() for th in document.cssselect("thead th")]
    (row,) = _audit_log_rows(document)
    assert headers == ["Details", "When", "Who", "What", "Target"]
    assert row[1:4] == ["Ada Admin", "Cohort created", "Spring cohort"]
    assert _row_details(document, "body") == ["Reason because"]


@pytest.mark.django_db
def test_the_audit_row_toggle_is_named_by_the_label_not_the_action_code(
    staff_client: Client,
):
    """The row-detail toggle used to be named after the raw action code."""
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation,
        target_label="Spring cohort",
        reason="because",
    )

    document = _get_document(staff_client, _audit_log_url(organisation))

    (toggle,) = document.cssselect("tbody button[aria-label^='More about']")
    assert toggle.get("aria-label") == "More about Cohort created: Spring cohort"


@pytest.mark.django_db
def test_the_audit_log_renders_its_empty_state(staff_client: Client):
    organisation = OrganisationFactory()

    response = staff_client.get(_audit_log_url(organisation))

    template_names = [t.name for t in response.templates]
    assert "panel_framework/partials/table_empty.html" in template_names


@pytest.mark.django_db
def test_the_audit_log_escapes_a_target_label_in_the_table_and_the_card(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="<b>bold</b>")

    html = staff_client.get(_audit_log_url(organisation)).content.decode()

    assert "&lt;b&gt;bold&lt;/b&gt;" in html
    assert "<b>bold</b>" not in html
    assert html.count("&lt;b&gt;bold&lt;/b&gt;") >= 2


@pytest.mark.django_db
def test_the_audit_log_filters_narrow_by_who_what_and_when(staff_client: Client):
    organisation = OrganisationFactory()
    ada = UserFactory(first_name="Ada", last_name="Admin")
    AuditLogEntryFactory(
        target=organisation, actor=ada, action="cohort.created", target_label="Match"
    )
    AuditLogEntryFactory(
        target=organisation,
        actor=ada,
        action="role.assigned",
        target_label="Wrong action",
    )
    AuditLogEntryFactory(
        target=organisation,
        actor=None,
        action="cohort.created",
        target_label="Wrong actor",
    )

    document = _get_document(
        staff_client,
        f"{_audit_log_url(organisation)}?audit_log-who={ada.pk}&audit_log-what=cohort.created&audit_log-when=today",
    )

    assert [row[3] for row in _audit_log_rows(document)] == ["Match"]


@pytest.mark.django_db
def test_a_tampered_filter_value_renders_the_unfiltered_list(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="One")
    AuditLogEntryFactory(target=organisation, target_label="Two")

    document = _get_document(
        staff_client,
        f"{_audit_log_url(organisation)}?audit_log-who=not-a-user&audit_log-what=bogus.code&audit_log-when=forever",
    )

    assert len(_audit_log_rows(document)) == 2


@pytest.mark.django_db
def test_the_filtered_audit_log_empty_state_offers_a_clear_link(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, action="cohort.created")

    response = staff_client.get(
        f"{_audit_log_url(organisation)}?audit_log-what=role.assigned"
    )

    html = response.content.decode()
    template_names = [t.name for t in response.templates]
    assert "panel_framework/partials/table_empty.html" in template_names
    assert "No entries match these filters." in html
    assert "Clear filters" in html


def _record_run(
    organisation: Organisation,
    learners: Sequence[object],
    run_id: uuid.UUID,
    target_label: str = "Spring cohort",
) -> None:
    for learner in learners:
        record_entry(
            action="learner.deactivated",
            actor=None,
            target=cast(Model, learner),
            target_label=target_label,
            organisation=organisation,
            run_id=run_id,
        )
    record_run_summary(
        action="bulk_action.completed",
        run_id=run_id,
        organisation=organisation,
        actor=None,
        counts={"changed": len(learners), "skipped": 0, "failed": 0},
    )


@pytest.mark.django_db
def test_a_bulk_run_is_one_audit_log_row_listing_fifty_entries_and_the_rest(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learners = [LearnerFactory(organisation=organisation) for _ in range(60)]
    _record_run(organisation, learners, uuid4(), target_label="<b>bold</b>")

    response = staff_client.get(_audit_log_url(organisation))

    document = lxml.html.fromstring(response.content)
    (row,) = _audit_log_rows(document)
    (detail,) = document.cssselect("tbody tr[data-row-detail]")
    (card_detail,) = document.cssselect("li [data-row-detail]")
    html = response.content.decode()
    assert (
        row[2].startswith("Bulk action completed"),
        "60 changed, 0 skipped, 0 failed" in " ".join(detail.text_content().split()),
        "60 changed, 0 skipped, 0 failed"
        in " ".join(card_detail.text_content().split()),
        len(detail.cssselect("li")),
        "and 10 more" in detail.text_content(),
        "<b>bold</b>" in html,
        "&lt;b&gt;bold&lt;/b&gt;" in html,
    ) == (True, True, True, 50, True, False, True)


@pytest.mark.django_db
def test_a_bulk_runs_entry_shows_on_the_learners_history_tab(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    _record_run(organisation, [learner], uuid4())

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [row[2] for row in rows] == ["Learner deactivated"]


@pytest.mark.django_db
def test_a_run_in_another_organisation_with_the_same_run_id_is_not_listed(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    other = OrganisationFactory()
    run_id = uuid4()
    _record_run(organisation, [LearnerFactory(organisation=organisation)], run_id)
    _record_run(
        other,
        [LearnerFactory(organisation=other), LearnerFactory(organisation=other)],
        run_id,
    )

    document = _get_document(staff_client, _audit_log_url(organisation))

    (detail,) = document.cssselect("tbody tr[data-row-detail]")
    assert len(detail.cssselect("li")) == 1


@pytest.mark.django_db
def test_the_audit_log_renders_three_runs_within_a_query_budget(
    staff_client: Client, django_assert_max_num_queries
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    for _ in range(3):
        _record_run(organisation, [learner] * 5, uuid4())

    with django_assert_max_num_queries(QUERY_BUDGET):
        response = staff_client.get(_audit_log_url(organisation))

    assert len(_audit_log_rows(lxml.html.fromstring(response.content))) == 3


def _audit_row_cells(
    document: lxml.html.HtmlElement, target_label: str
) -> dict[str, lxml.html.HtmlElement]:
    """The Who and Target cells of the Audit log row whose Target reads `target_label`."""
    for row in document.cssselect("tbody tr:not([data-row-detail])"):
        cells = row.cssselect("td")
        if _visible_text(cells[4]).endswith(target_label):
            return {"who": cells[2], "target": cells[4]}
    raise AssertionError(f"no Audit log row targets {target_label!r}")


def _avatar_slot(cell: lxml.html.HtmlElement) -> str | None:
    """The `panel-avatar-N` class of the initials circle in `cell`, if it has one."""
    for element in cell.iter():
        for name in (element.get("class") or "").split():
            if name.startswith("panel-avatar-"):
                return name
    return None


def _audit_log_document(
    staff_client: Client, organisation: Organisation
) -> lxml.html.HtmlElement:
    return _get_document(staff_client, _audit_log_url(organisation))


@pytest.mark.django_db
def test_the_system_actor_shows_the_settings_icon_and_no_chip(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours", actor_label="")

    cells = _audit_row_cells(_audit_log_document(staff_client, organisation), "Ours")

    who = cells["who"]
    assert (
        len(who.cssselect("svg[data-icon='settings']")),
        _visible_text(who),
        _avatar_slot(who),
    ) == (1, "System", None)


@pytest.mark.django_db
def test_a_deleted_actor_shows_the_user_icon_beside_the_stored_name(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation, target_label="Ours", actor=None, actor_label="Gone Person"
    )

    cells = _audit_row_cells(_audit_log_document(staff_client, organisation), "Ours")

    who = cells["who"]
    assert (
        len(who.cssselect("svg[data-icon='user']")),
        _visible_text(who),
        _avatar_slot(who),
    ) == (1, "Gone Person", None)


@pytest.mark.django_db
@pytest.mark.parametrize("learner_is_active", [True, False])
def test_a_person_target_has_the_same_avatar_colour_as_that_person_as_actor(
    staff_client: Client, learner_is_active: bool
):
    organisation = OrganisationFactory()
    user = UserFactory(first_name="Pat", last_name="Person")
    learner = LearnerFactory(
        organisation=organisation, user=user, is_active=learner_is_active
    )
    member = StaffMemberFactory(organisation=organisation, user=user)
    AuditLogEntryFactory(
        target=organisation,
        target_label="As actor",
        actor=user,
        actor_label="Pat Person",
    )
    for target, label in (
        (user, "User target"),
        (learner, "Learner target"),
        (member, "Member target"),
    ):
        AuditLogEntryFactory(
            target=target,
            target_label=label,
            organisation=organisation,
            action="learner.deactivated",
        )

    document = _audit_log_document(staff_client, organisation)

    actor_slot = _avatar_slot(_audit_row_cells(document, "As actor")["who"])
    target_cells = [
        _audit_row_cells(document, label)["target"]
        for label in ("User target", "Learner target", "Member target")
    ]
    assert actor_slot is not None
    assert [_avatar_slot(cell) for cell in target_cells] == [actor_slot] * 3
    assert [len(cell.cssselect("[aria-hidden='true']")) for cell in target_cells] == [
        1
    ] * 3


@pytest.mark.django_db
def test_the_learners_list_avatar_colours_match_the_audit_log_for_the_same_people(
    staff_client: Client,
):
    """The learners list keyed the avatar on the learner row's pk, so people
    were different colours there than in the audit log, which keys on the user.
    Many people are checked because any one pair could match by chance."""
    organisation = OrganisationFactory()
    names = [f"Person{letter}" for letter in "ABCDEFGH"]
    for name in names:
        user = UserFactory(first_name=name, last_name="Tester")
        LearnerFactory(organisation=organisation, user=user)
        AuditLogEntryFactory(
            target=organisation, target_label=name, actor=user, actor_label=name
        )

    audit_document = _audit_log_document(staff_client, organisation)
    audit_slots = [
        _avatar_slot(_audit_row_cells(audit_document, name)["who"]) for name in names
    ]
    list_document = _get_document(
        staff_client, _interface_url(organisation.slug, "learners")
    )
    list_slots = []
    for name in names:
        (row,) = [
            row
            for row in list_document.cssselect("tbody tr")
            if name in row.text_content()
        ]
        list_slots.append(_avatar_slot(row))

    assert list_slots == audit_slots


@pytest.mark.django_db
def test_a_learner_target_whose_row_was_deleted_shows_the_user_icon_and_stored_label(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    AuditLogEntryFactory(
        target=learner,
        target_label="Gone Learner",
        organisation=organisation,
        action="learner.deactivated",
    )
    learner.delete()

    cells = _audit_row_cells(
        _audit_log_document(staff_client, organisation), "Gone Learner"
    )

    target = cells["target"]
    assert (len(target.cssselect("svg[data-icon='user']")), _avatar_slot(target)) == (
        1,
        None,
    )


@pytest.mark.django_db
def test_a_cohort_target_renders_plain_text_with_no_circle(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    AuditLogEntryFactory(
        target=cohort, target_label="Spring cohort", organisation=organisation
    )

    cells = _audit_row_cells(
        _audit_log_document(staff_client, organisation), "Spring cohort"
    )

    target = cells["target"]
    assert (len(target.cssselect("[aria-label]")), _avatar_slot(target)) == (0, None)


@pytest.mark.django_db
def test_a_chip_for_a_user_with_no_name_takes_its_initials_from_the_email_label(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    user = UserFactory(first_name="", last_name="")
    AuditLogEntryFactory(
        target=organisation,
        target_label="Ours",
        actor=user,
        actor_label="zed@example.com",
    )

    cells = _audit_row_cells(_audit_log_document(staff_client, organisation), "Ours")

    assert _visible_text(cells["who"]).split()[0] == "Z"


@pytest.mark.django_db
def test_a_person_label_with_markup_renders_escaped(staff_client: Client):
    organisation = OrganisationFactory()
    user = UserFactory()
    AuditLogEntryFactory(
        target=organisation,
        target_label="Ours",
        actor=user,
        actor_label="<b>bold</b>",
    )

    response = staff_client.get(_audit_log_url(organisation))

    html = response.content.decode()
    assert ("<b>bold</b>" in html, "&lt;b&gt;bold&lt;/b&gt;" in html) == (False, True)


@pytest.mark.django_db
def test_the_audit_log_renders_three_runs_of_learner_entries_within_a_query_budget(
    staff_client: Client, django_assert_max_num_queries
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    for _ in range(3):
        _record_run(
            organisation, [learner] * 5, uuid4(), target_label=learner.user.email
        )

    with django_assert_max_num_queries(QUERY_BUDGET + 3):
        response = staff_client.get(_audit_log_url(organisation))

    assert len(_audit_log_rows(lxml.html.fromstring(response.content))) == 3


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


# The learner page's Messages tab: the educator's own conversation with the
# learner, and the composer that posts back into the tab.


def _tab_url(learner: Learner) -> str:
    return _msg_url(learner.organisation, f"learners/{learner.pk}/__tabs/messages")


def _send_url(learner: Learner) -> str:
    return f"{_tab_url(learner)}/__panels/conversation/__actions/send"


def _tab_document(client: Client, learner: Learner) -> lxml.html.HtmlElement:
    return _get_document(client, _tab_url(learner))


@pytest.mark.django_db
@messages_section
class TestLearnerMessagesTab:
    def test_the_tab_is_in_the_learner_pages_tab_row(self, msg_client_for):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)

        document = _learner_page(msg_client_for(educator), learner)

        assert document.xpath(f"//a[@href='{_tab_url(learner)}']")

    def test_the_tab_is_absent_and_its_url_404s_when_messaging_is_off(
        self, msg_client_for, settings
    ):
        settings.MESSAGING_ENABLED = False
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        client = msg_client_for(educator)

        document = _learner_page(client, learner)

        assert not document.xpath(f"//a[@href='{_tab_url(learner)}']")
        assert client.get(_tab_url(learner)).status_code == 404

    def test_it_shows_the_educators_own_conversation_and_not_a_colleagues(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        colleague = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        own = _msg_conversation(educator, learner.user)
        MessageFactory(conversation=own, sender=learner.user, body="for me")
        theirs = _msg_conversation(colleague, learner.user)
        MessageFactory(conversation=theirs, sender=learner.user, body="for them")

        document = _tab_document(msg_client_for(educator), learner)

        for section in document.xpath("//section[@data-panel='others']"):
            section.getparent().remove(section)
        text = document.text_content()
        assert "for me" in text
        assert "for them" not in text

    def test_the_thread_inside_the_panel_draws_no_header_of_its_own(
        self, msg_client_for
    ):
        """The panel's Messages title heads the conversation, so the thread
        adds no second header (avatar, name and a rule under them), and it
        keeps the card's padding and rounded corners."""
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        conversation = _msg_conversation(educator, learner.user)
        MessageFactory(conversation=conversation, sender=learner.user, body="hi")

        document = _tab_document(msg_client_for(educator), learner)

        (panel,) = document.xpath("//section[@data-panel='conversation']")
        (pane,) = panel.xpath(".//section[@x-data='conversationThread']")
        assert not pane.xpath(".//header")
        assert not pane.xpath(".//h1 | .//h2 | .//h3")
        classes = pane.get("class").split()
        assert "rounded-b-lg" in classes
        assert "sm:[&_[role=log]]:px-6" in classes

    def test_a_learner_with_no_conversation_shows_a_prompt_and_a_composer_posting_to_the_tab(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)

        document = _tab_document(msg_client_for(educator), learner)

        assert "No messages with Ada Lovelace yet." in document.text_content()
        composer = document.xpath("//form[@id='composer']")[0]
        assert composer.get("hx-post") == _send_url(learner)
        region_id = document.xpath("//section[@data-panel='conversation']")[0].get("id")
        assert composer.get("hx-target") == f"#{region_id}"
        assert composer.get("hx-swap") == "outerHTML"

    def test_opening_the_tab_moves_the_educators_read_marker(self, msg_client_for):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        conversation = _msg_conversation(educator, learner.user)
        MessageFactory(conversation=conversation, sender=learner.user, body="hi")
        assert unread_conversation_count(educator) == 1

        _tab_document(msg_client_for(educator), learner)

        assert unread_conversation_count(educator) == 0

    def test_an_educator_of_another_organisation_gets_404(self, msg_client_for):
        organisation = OrganisationFactory()
        learner = _msg_learner(organisation)
        outsider = _msg_educator(OrganisationFactory())

        response = msg_client_for(outsider).get(_tab_url(learner))

        assert response.status_code == 404

    def test_an_organisation_admin_sees_the_learners_educator_conversations_but_not_peers_or_their_own(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        admin = _msg_educator(organisation)
        colleague = _msg_educator(organisation)
        peer = _msg_learner(organisation, first_name="Peer", last_name="Person")
        learner = _msg_learner(organisation)
        own = _msg_conversation(admin, learner.user)
        MessageFactory(conversation=own, sender=admin, body="my own words")
        theirs = _msg_conversation(colleague, learner.user)
        MessageFactory(conversation=theirs, sender=colleague, body="colleague words")
        among_peers = _msg_conversation(peer.user, learner.user)
        MessageFactory(conversation=among_peers, sender=peer.user, body="peer words")

        document = _tab_document(msg_client_for(admin), learner)

        (section,) = document.xpath("//section[@data-panel='others']")
        text = section.text_content()
        assert "Other educator conversations" in text
        assert colleague.display_name in text
        assert "colleague words" in text
        assert "my own words" not in text
        assert "peer words" not in text
        assert "Peer Person" not in text

    def test_a_site_admin_sees_the_list(self, msg_client_for, mock_site_context):
        organisation = OrganisationFactory()
        site_admin = cast(User, UserFactory(staff=True))
        _grant(site_admin, "site_admin", mock_site_context)
        colleague = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        _msg_conversation(colleague, learner.user)

        document = _tab_document(msg_client_for(site_admin), learner)

        assert colleague.display_name in document.text_content()
        assert document.xpath("//section[@data-panel='others']//h2")

    @pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
    def test_a_cohort_role_sees_no_list(self, msg_client_for, role):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        learner = _msg_learner(organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        educator = cast(User, UserFactory(staff=True))
        _grant(educator, role, cohort)
        colleague = _msg_educator(organisation)
        _msg_conversation(colleague, learner.user)

        document = _tab_document(msg_client_for(educator), learner)

        assert "Other educator conversations" not in document.text_content()
        assert not document.xpath("//*[@id='oversight-heading']")

    def test_a_deactivated_learner_shows_the_empty_state(self, msg_client_for):
        organisation = OrganisationFactory()
        admin = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        _msg_conversation(_msg_educator(organisation), learner.user)
        learner.is_active = False
        learner.save()

        document = _tab_document(msg_client_for(admin), learner)

        assert "No other educator conversations." in document.text_content()

    def test_the_list_renders_when_the_admins_own_area_is_hidden(
        self, msg_client_for, monkeypatch
    ):
        organisation = OrganisationFactory()
        admin = _msg_educator(organisation)
        colleague = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        _msg_conversation(colleague, learner.user)
        monkeypatch.setattr(
            "freedom_ls.educator_interface.views.own_conversation_with",
            lambda request, learner: OwnConversation(None, False),
        )

        document = _tab_document(msg_client_for(admin), learner)

        assert not document.xpath("//form[@id='composer']")
        assert colleague.display_name in document.text_content()

    def test_the_first_send_creates_the_conversation_and_rerenders_the_tab(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Welcome aboard", "client_key": str(uuid4())}
        )

        assert response.status_code == 200
        assert "HX-Location" not in response
        assert json.loads(response["HX-Trigger"]) == {"conversationChanged": {}}
        conversation = inbox_for(educator).get()
        assert conversation.messages.get().body == "Welcome aboard"
        page = lxml.html.fromstring(response.content.decode())
        assert "Welcome aboard" in page.xpath("//*[@id='thread-log']")[0].text_content()

    def test_a_reply_into_an_existing_conversation_rerenders_the_tab(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        conversation = _msg_conversation(educator, learner.user)

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Second thoughts", "client_key": str(uuid4())}
        )

        assert response.status_code == 200
        assert "HX-Location" not in response
        assert json.loads(response["HX-Trigger"]) == {"conversationChanged": {}}
        assert conversation.messages.get().body == "Second thoughts"
        page = lxml.html.fromstring(response.content.decode())
        assert page.xpath("//*[@id='thread-log']")

    def test_a_refused_send_answers_422_with_the_draft_and_the_alert(
        self, msg_client_for, monkeypatch
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        monkeypatch.setattr(
            "freedom_ls.educator_interface.views.send_message",
            lambda **kwargs: SendResult(refusal=MessagingRefusal.NO_RELATIONSHIP),
        )

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Welcome aboard", "client_key": str(uuid4())}
        )

        assert response.status_code == 422
        page = lxml.html.fromstring(response.content.decode())
        assert page.xpath("//*[@role='alert'][not(@x-show)]")
        textarea = page.xpath("//textarea[@name='body']")[0]
        assert "Welcome aboard" in textarea.text_content()
        assert not inbox_for(educator).exists()

    def test_a_first_send_refused_after_starting_closed_keeps_the_draft_and_the_alert(
        self, msg_client_for, monkeypatch
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        monkeypatch.setattr(
            "freedom_ls.educator_interface.views.own_conversation_with",
            lambda request, learner: OwnConversation(None, False),
        )
        monkeypatch.setattr(
            "freedom_ls.educator_interface.views.send_message",
            lambda **kwargs: SendResult(refusal=MessagingRefusal.NO_RELATIONSHIP),
        )

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Welcome aboard", "client_key": str(uuid4())}
        )

        assert response.status_code == 422
        page = lxml.html.fromstring(response.content.decode())
        assert page.xpath("//*[@role='alert'][not(@x-show)]")
        textarea = page.xpath("//textarea[@name='body']")[0]
        assert "Welcome aboard" in textarea.text_content()

    def test_a_post_with_messaging_off_is_denied_and_stores_nothing(
        self, msg_client_for, settings
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        settings.MESSAGING_ENABLED = False

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Welcome aboard", "client_key": str(uuid4())}
        )

        assert response.status_code in {403, 404}
        assert not inbox_for(educator).exists()


def _view_conversation_url(learner: Learner) -> str:
    return f"{_tab_url(learner)}/__panels/others/__actions/view_conversation"


def _older_url(
    learner: Learner,
    conversation_pk: object,
    cursor: str,
    organisation: Organisation | None = None,
) -> str:
    slug = (organisation or learner.organisation).slug
    base = reverse(
        "educator_interface:oversight_thread_older",
        kwargs={
            "organisation_slug": slug,
            "learner_pk": str(learner.pk),
            "conversation_pk": str(conversation_pk),
        },
    )
    return f"{base}?before={quote(cursor)}" if cursor else base


def _open_conversation(
    client: Client, learner: Learner, conversation: object, **extra: str
):
    return client.get(
        f"{_view_conversation_url(learner)}?conversation={conversation}",
        HTTP_HX_REQUEST="true",
        **extra,
    )


def _viewed_entries() -> list[AuditLogEntry]:
    return list(AuditLogEntry.unscoped.filter(action="conversation.viewed"))


def _read_markers(conversation: Conversation) -> list[str]:
    return sorted(str(p.last_read_at) for p in conversation.participants.all())


@pytest.mark.django_db
@messages_section
class TestOversight:
    @pytest.fixture
    def scene(self):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        conversation = _msg_conversation(educator, learner.user)
        MessageFactory(conversation=conversation, sender=educator, body="oversight me")
        return organisation, educator, learner, conversation

    def test_the_oversight_dialog_ends_in_a_close_button(self, msg_client_for, scene):
        organisation, _educator, learner, conversation = scene
        admin = _msg_educator(organisation)

        response = _open_conversation(msg_client_for(admin), learner, conversation.pk)

        page = lxml.html.fromstring(response.content.decode())
        assert [b.text_content().strip() for b in page.cssselect("footer button")][
            -1:
        ] == ["Close"]

    def test_an_organisation_admin_reads_the_thread_read_only(
        self, msg_client_for, scene
    ):
        organisation, educator, learner, conversation = scene
        admin = _msg_educator(organisation)

        response = _open_conversation(msg_client_for(admin), learner, conversation.pk)

        assert response.status_code == 200
        page = lxml.html.fromstring(response.content.decode())
        text = " ".join(page.text_content().split())
        assert "oversight me" in text
        assert f"Conversation with {educator.display_name}" in text
        assert (
            "Read only. You are viewing this conversation as an organisation admin."
            in text
        )
        assert not page.xpath("//*[@id='composer']")

    def test_a_site_admin_is_named_as_one(
        self, msg_client_for, scene, mock_site_context
    ):
        _, _, learner, conversation = scene
        site_admin = cast(User, UserFactory(staff=True))
        _grant(site_admin, "site_admin", mock_site_context)

        response = _open_conversation(
            msg_client_for(site_admin), learner, conversation.pk
        )

        assert "as a site admin." in " ".join(response.content.decode().split())

    def test_the_open_writes_one_entry_naming_the_learner(self, msg_client_for, scene):
        organisation, educator, learner, conversation = scene
        admin = _msg_educator(organisation)

        _open_conversation(msg_client_for(admin), learner, conversation.pk)

        (entry,) = _viewed_entries()
        assert entry.target_label == f"Conversation with {educator.display_name}"
        assert entry.actor == admin
        assert entry.organisation == organisation
        assert entry.target == conversation
        assert subject_key(learner) in entry.subjects

    def test_a_second_open_writes_a_second_entry(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))

        _open_conversation(client, learner, conversation.pk)
        _open_conversation(client, learner, conversation.pk)

        assert len(_viewed_entries()) == 2

    def test_the_open_moves_no_read_marker(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        before = _read_markers(conversation)

        _open_conversation(
            msg_client_for(_msg_educator(organisation)), learner, conversation.pk
        )

        assert _read_markers(conversation) == before

    def test_the_entry_shows_on_the_learners_history_tab(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))
        _open_conversation(client, learner, conversation.pk)

        text = _learner_page(client, learner, "history").text_content()

        assert "Conversation viewed" in text

    def test_a_plain_get_is_404_and_writes_nothing(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))

        response = client.get(
            f"{_view_conversation_url(learner)}?conversation={conversation.pk}"
        )

        assert response.status_code == 404
        assert _viewed_entries() == []

    def test_a_conversation_outside_the_oversight_set_is_404(
        self, msg_client_for, scene
    ):
        organisation, _, learner, _ = scene
        client = msg_client_for(_msg_educator(organisation))
        peer = _msg_learner(organisation, first_name="Peer")
        peer_conversation = _msg_conversation(peer.user, learner.user)
        stranger = _msg_learner(OrganisationFactory())
        foreign = _msg_conversation(_msg_educator(stranger.organisation), stranger.user)

        for target in (peer_conversation.pk, foreign.pk, uuid4(), "not-a-uuid", ""):
            response = _open_conversation(client, learner, target)
            assert response.status_code == 404, target
        assert _viewed_entries() == []

    def test_the_viewers_own_conversation_is_404_and_writes_nothing(
        self, msg_client_for, scene
    ):
        _, educator, learner, conversation = scene
        client = msg_client_for(educator)

        opened = _open_conversation(client, learner, conversation.pk)
        older = client.get(
            _older_url(
                learner, conversation.pk, encode_cursor(conversation.messages.get())
            ),
            HTTP_HX_REQUEST="true",
        )

        assert opened.status_code == 404
        assert older.status_code == 404
        assert _viewed_entries() == []

    def test_a_cohort_admin_is_denied_and_nothing_is_written(
        self, msg_client_for, scene
    ):
        organisation, _, learner, conversation = scene
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        cohort_admin = cast(User, UserFactory(staff=True))
        _grant(cohort_admin, "cohort_admin", cohort)

        response = _open_conversation(
            msg_client_for(cohort_admin), learner, conversation.pk
        )

        # The panel that holds the action is not shown to them, so its
        # address is a 404 like any other out-of-scope path.
        assert response.status_code == 404
        assert _viewed_entries() == []

    def test_the_action_is_denied_when_messaging_is_off(
        self, msg_client_for, scene, settings
    ):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))
        settings.MESSAGING_ENABLED = False

        response = _open_conversation(client, learner, conversation.pk)

        assert response.status_code in (403, 404)
        assert _viewed_entries() == []

    def test_a_post_is_404(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))

        response = client.post(
            _view_conversation_url(learner),
            {"conversation": str(conversation.pk)},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404
        assert _viewed_entries() == []

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

    def test_the_list_rows_open_the_conversation_in_the_modal(
        self, msg_client_for, scene
    ):
        organisation, _, learner, conversation = scene
        admin = _msg_educator(organisation)

        document = _tab_document(msg_client_for(admin), learner)

        (row,) = document.xpath("//section[@data-panel='others']//li/button")
        assert row.get("hx-get") == (
            f"{_view_conversation_url(learner)}?conversation={conversation.pk}"
        )
        assert row.get("hx-target") == "#app-modal-body"


# bulk run status, polled by the table a background run was started from.
# The route is the framework's; these cover its wiring into this interface
# (the organisation scope, the refresh event and the notification hooks).


def _run_for(user: User, organisation: Organisation, **fields: object):
    return BulkActionRun.objects.create(
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
    educator_views.LearnerDataTable,
    educator_views.CohortLearnerDataTable,
    educator_views.CohortDataTable,
    educator_views.LearnerCohortDataTable,
    educator_views.CourseDataTable,
    educator_views.CohortCourseRegistrationDataTable,
    educator_views.CourseCohortRegistrationDataTable,
    educator_views.CourseLearnerRegistrationDataTable,
    educator_views.StaffDataTable,
    educator_views.OrganisationAuditLogTable,
]


@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_the_first_use_message_is_a_sentence(table: type[DataTable]) -> None:
    assert table.empty_message.endswith(".")
    assert table.empty_message != DataTable.empty_message


@pytest.mark.parametrize(
    "panel", [educator_views.LearnerHistoryPanel, educator_views.CohortHistoryPanel]
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


def _learner_in_state(state: str) -> Learner:
    user = UserFactory()
    if state == "pending":
        user.set_unusable_password()
        user.save()
    learner = cast(
        Learner,
        LearnerFactory(
            user=user, organisation=OrganisationFactory(), is_active=state != "inactive"
        ),
    )
    return learner


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("state", "label", "tone"),
    [
        ("active", "Active", "success"),
        ("pending", "Pending", "info"),
        ("inactive", "Inactive", "muted"),
    ],
)
def test_learner_status_badge_has_one_label_and_tone_per_state(
    mock_site_context, state: str, label: str, tone: str
):
    badge = learner_status_badge(_learner_in_state(state))

    assert (badge.label, badge.tone) == (label, tone)


@pytest.mark.parametrize(
    ("is_active", "label", "tone"),
    [(True, "Active", "success"), (False, "Inactive", "muted")],
)
def test_active_status_badge_has_one_label_and_tone_per_state(
    is_active: bool, label: str, tone: str
):
    badge = active_status_badge(is_active)

    assert (badge.label, badge.tone) == (label, tone)


@pytest.mark.django_db
def test_the_history_tab_names_a_nameless_actor_by_their_email(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    actor = UserFactory(first_name="", last_name="", email="nameless@example.com")
    record_entry(
        action="learner.deactivated",
        actor=actor,
        target=learner,
        target_label=learner.user.display_name,
        organisation=learner.organisation,
    )

    document = _learner_page(staff_client, learner, "history")

    # The name beside the avatar; the avatar's initial is aria-hidden.
    names = [
        span.text_content().strip()
        for span in document.cssselect(
            "[data-tab-set] tbody tr:not([data-row-detail]) span.truncate"
        )
    ]
    assert names == ["nameless@example.com"]


def _get_table_fragment(client: Client, path: str):
    return client.get(path, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="history-table")


@pytest.mark.django_db
def test_a_table_fragment_of_a_learner_from_another_organisation_answers_the_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    elsewhere = LearnerFactory(organisation=OrganisationFactory())

    response = _get_table_fragment(
        staff_client, _interface_url(organisation.slug, f"learners/{elsewhere.pk}")
    )

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_a_table_fragment_of_an_unknown_learner_answers_the_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = _get_table_fragment(
        staff_client, _interface_url(organisation.slug, f"learners/{uuid.uuid4()}")
    )

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_the_out_of_scope_dialog_is_byte_equal_to_the_unavailable_template(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    elsewhere = LearnerFactory(organisation=OrganisationFactory())

    response = _get_table_fragment(
        staff_client, _interface_url(organisation.slug, f"learners/{elsewhere.pk}")
    )

    assert response.content.decode() == render_to_string(
        "panel_framework/partials/action_unavailable.html"
    )


@pytest.mark.django_db
def test_a_plain_request_for_an_unknown_learner_gets_the_page_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = staff_client.get(
        _interface_url(organisation.slug, f"learners/{uuid.uuid4()}")
    )

    assert response.status_code == 404
    assert "data-htmx-swap-error" not in response.content.decode()


@pytest.mark.django_db
def test_the_audit_log_what_filter_is_a_grouped_checklist_with_one_apply(
    staff_client: Client,
):
    """Many actions as a chip cloud were unreadable; the filter is a checkbox
    per action under its group, applied once, in the toolbar and the sheet."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _audit_log_url(organisation))

    # The popover form in the toolbar; the sheet holds its own copy.
    (toolbar_form,) = [
        form
        for form in document.cssselect("details form[hx-get]")
        if form.cssselect("input[type='checkbox'][name='audit_log-what']")
    ]
    legends = [
        legend.text_content().strip() for legend in toolbar_form.cssselect("legend")
    ]
    assert legends == [
        "Learners",
        "Cohort membership",
        "Course registrations",
        "Cohorts",
        "Staff and roles",
        "Other",
    ]
    assert toolbar_form.xpath(".//button[@type='submit'][normalize-space()='Apply']")
    assert "Learner added to cohort" in toolbar_form.text_content()
    (sheet,) = document.cssselect("dialog#audit_log-sheet")
    summaries = [
        summary.text_content().strip() for summary in sheet.cssselect("details summary")
    ]
    assert summaries == legends
    assert not sheet.cssselect("label.rounded-full")


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


def _audit_log_export(
    client: Client, organisation: Organisation, **filters: str
) -> tuple[list[str], list[list[str]], str]:
    response = client.get(
        _audit_log_url(organisation),
        {"audit_log-export": "csv", **filters},
    )
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    header, *rows = list(csv.reader(io.StringIO(body, newline="")))
    return header, rows, response["Content-Disposition"]


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
def test_the_audit_log_toolbar_offers_the_csv_export(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation)

    document = _audit_log_document(staff_client, organisation)

    links = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert links
    assert all("audit_log-export=csv" in a.get("href") for a in links)


@pytest.mark.django_db
def test_the_audit_log_export_honours_the_who_filter(staff_client: Client):
    organisation = OrganisationFactory()
    ada = UserFactory(first_name="Ada", last_name="Admin")
    AuditLogEntryFactory(target=organisation, actor=ada, target_label="Match")
    AuditLogEntryFactory(target=organisation, actor=None, target_label="Other actor")

    _header, rows, _disposition = _audit_log_export(
        staff_client, organisation, **{"audit_log-who": str(ada.pk)}
    )

    assert [row[5] for row in rows] == ["Match"]


@pytest.mark.django_db
def test_the_audit_log_export_honours_the_what_filter(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation, action="cohort.created", target_label="Match"
    )
    AuditLogEntryFactory(
        target=organisation, action="role.assigned", target_label="Other action"
    )

    _header, rows, _disposition = _audit_log_export(
        staff_client, organisation, **{"audit_log-what": "cohort.created"}
    )

    assert [row[5] for row in rows] == ["Match"]


@pytest.mark.django_db
def test_the_audit_log_export_honours_the_when_filter(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Recent")
    AuditLogEntryFactory(
        target=organisation,
        target_label="Old",
        created_at=timezone.now() - timedelta(days=10),
    )

    _header, rows, _disposition = _audit_log_export(
        staff_client, organisation, **{"audit_log-when": "today"}
    )

    assert [row[5] for row in rows] == ["Recent"]


@pytest.mark.django_db
def test_the_audit_log_export_is_named_for_the_organisation(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation)

    _header, _rows, disposition = _audit_log_export(staff_client, organisation)

    assert disposition == (
        f'attachment; filename="audit_log-{organisation.slug}-{timezone.localdate():%Y-%m-%d}.csv"'
    )


@pytest.mark.django_db
def test_the_audit_log_export_holds_a_runs_summary_and_every_per_object_entry(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learners = [LearnerFactory(organisation=organisation) for _ in range(3)]
    run_id = uuid4()
    _record_run(organisation, learners, run_id)

    _header, rows, _disposition = _audit_log_export(staff_client, organisation)

    assert (len(rows), {row[8] for row in rows}) == (4, {str(run_id)})


@pytest.mark.django_db
def test_a_what_filter_on_the_per_object_action_drops_the_runs_summary(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learners = [LearnerFactory(organisation=organisation) for _ in range(3)]
    _record_run(organisation, learners, uuid4())

    _header, rows, _disposition = _audit_log_export(
        staff_client, organisation, **{"audit_log-what": "learner.deactivated"}
    )

    assert [row[3] for row in rows] == ["Learner deactivated"] * 3


@pytest.mark.django_db
def test_the_audit_log_export_leaves_out_another_organisations_entries(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours")
    AuditLogEntryFactory(target=OrganisationFactory(), target_label="Theirs")

    _header, rows, _disposition = _audit_log_export(staff_client, organisation)

    assert [row[5] for row in rows] == ["Ours"]


@pytest.mark.django_db
def test_the_audit_log_export_leaves_out_another_sites_entries(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours")
    with site_context(SiteFactory()):
        AuditLogEntryFactory(target=organisation, target_label="Other site")

    _header, rows, _disposition = _audit_log_export(staff_client, organisation)

    assert [row[5] for row in rows] == ["Ours"]


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


@pytest.mark.django_db
def test_the_audit_log_export_records_its_scope_and_applied_filters(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    orla = UserFactory(first_name="Orla", last_name="Admin")
    AuditLogEntryFactory(target=organisation, actor=orla, action="learner.deactivated")

    _audit_log_export(
        staff_client,
        organisation,
        **{"audit_log-who": str(orla.pk), "audit_log-what": "learner.deactivated"},
    )

    entry = AuditLogEntry.objects.get(action="audit_log.exported")
    assert entry.details == {
        "scope": "organisation",
        "scope_label": "",
        "count": 1,
        "filters": "Who: Orla Admin, What: Learner deactivated",
    }


@pytest.mark.django_db
def test_the_audit_log_export_omits_its_own_entry_and_a_second_export_holds_it(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours")

    _header, first_rows, _disposition = _audit_log_export(staff_client, organisation)
    _header, second_rows, _disposition = _audit_log_export(staff_client, organisation)

    assert (
        [row[4] for row in first_rows if "exported" in row[4]],
        len([row for row in second_rows if "exported" in row[4]]),
    ) == ([], 1)


def _course_content_panel(client: Client, course: CourseModel) -> lxml.html.HtmlElement:
    organisation = OrganisationFactory()
    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )
    (panel,) = document.cssselect("section[data-panel='content']")
    return panel


def _outline_rows(panel: lxml.html.HtmlElement) -> list[lxml.html.HtmlElement]:
    return list(panel.cssselect("[aria-label='Course outline'] tbody tr"))


def _outline_numbers(panel: lxml.html.HtmlElement) -> list[str]:
    numbers = [
        cell.text_content().strip()
        for row in _outline_rows(panel)
        for cell in row.cssselect("td.tabular-nums")[:1]
    ]
    return [number for number in numbers if number]


@pytest.mark.django_db
def test_course_content_numbers_rows_in_collection_order(staff_client: Client):
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=1
    )
    part = CoursePartFactory(title="Warm up")
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=2)
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=1
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=FormFactory(), order=3
    )

    panel = _course_content_panel(staff_client, course)

    assert panel.cssselect(".panel-data-table table")
    assert _outline_numbers(panel) == ["1.", "2.", "3.", "3.1", "3.2", "4."]
    rows = _outline_rows(panel)
    first_cells = [cell.text_content().strip() for cell in rows[0].cssselect("td")]
    assert first_cells[:3] == ["", "Course details", "Course"]
    assert rows[0].cssselect("button[hx-get]")[0].text_content().strip() == "Preview"
    form_row = rows[-1]
    assert form_row.cssselect("svg")
    assert form_row.cssselect(".sr-only")[0].text_content().strip() == "Form"
    assert form_row.cssselect("td")[2].text_content().strip() == "Form"
    assert form_row.cssselect("button[hx-get]")[0].text_content().strip() == "Preview"
    assert panel.cssselect("header button") == []


@pytest.mark.django_db
def test_course_content_part_rows_are_expandable_buttons(staff_client: Client):
    course = CourseFactory()
    part = CoursePartFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=1
    )
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=1
    )

    panel = _course_content_panel(staff_client, course)

    (button,) = panel.cssselect("button[aria-controls]")
    assert button.get("aria-expanded") == "true"
    # aria-expanded carries the state, so the name holds no verb that would
    # be wrong once the group is collapsed.
    assert button.get("aria-label") == part.title
    row_ids = {node.get("id") for node in panel.cssselect("tbody tr[id]")}
    controlled = set(str(button.get("aria-controls")).split())
    assert len(controlled) == 2
    assert controlled <= row_ids
    assert button.xpath("ancestor::tr")[0].cssselect("button[hx-get]") == []


@pytest.mark.django_db
def test_a_multi_page_form_expands_into_one_row_per_page(staff_client: Client):
    course = CourseFactory()
    survey = FormFactory(title="Survey")
    first = FormPageFactory(form=survey, title="About you", order=0)
    FormPageFactory(form=survey, title="", order=1)
    quiz = FormFactory(title="Quiz")
    FormPageFactory(form=quiz, title="Only page", order=0)
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    survey_item = ContentCollectionItemFactory(
        collection_object=course, child_object=survey, order=1
    )
    ContentCollectionItemFactory(collection_object=course, child_object=quiz, order=2)

    panel = _course_content_panel(staff_client, course)

    assert _outline_numbers(panel) == ["1.", "2.", "2.1", "2.2", "3."]
    rows = _outline_rows(panel)
    survey_row, page_one, page_two, quiz_row = rows[2], rows[3], rows[4], rows[5]
    (toggle,) = survey_row.cssselect("button[aria-controls]")
    assert set(str(toggle.get("aria-controls")).split()) == {
        page_one.get("id"),
        page_two.get("id"),
    }
    (survey_trigger,) = survey_row.cssselect("button[hx-get]")
    assert survey_trigger.get("hx-get").endswith(f"?item={survey_item.pk}")
    (page_trigger,) = page_one.cssselect("button[hx-get]")
    assert page_trigger.get("hx-get").endswith(
        f"?item={survey_item.pk}&page={first.pk}"
    )
    assert page_trigger.get("aria-label") == "Preview Survey: About you"
    assert page_one.cssselect("td")[2].text_content().strip() == "Page"
    assert page_two.cssselect("td .font-medium")[0].text_content().strip() == "Page 2"
    assert quiz_row.cssselect("button[aria-controls]") == []
    (quiz_trigger,) = quiz_row.cssselect("button[hx-get]")
    assert "page=" not in str(quiz_trigger.get("hx-get"))


@pytest.mark.django_db
def test_course_content_empty_course_shows_empty_state(staff_client: Client):
    panel = _course_content_panel(staff_client, CourseFactory())

    assert "No content in this course yet." in panel.text_content()
    assert _outline_numbers(panel) == []
    assert len(_outline_rows(panel)) == 2


@pytest.mark.django_db
def test_course_content_empty_part_shows_empty_message(staff_client: Client):
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=CoursePartFactory(), order=0
    )

    panel = _course_content_panel(staff_client, course)

    assert "No items in this part." in panel.text_content()


@pytest.mark.django_db
@pytest.mark.parametrize("in_development", [True, False])
def test_course_content_callout_shows_only_while_in_development(
    staff_client: Client, in_development: bool
):
    course = CourseFactory(table_of_contents_in_development=in_development)

    panel = _course_content_panel(staff_client, course)

    assert ("Learners can't see this outline yet." in panel.text_content()) is (
        in_development
    )


@pytest.mark.django_db
def test_course_content_query_count_stays_bounded_as_children_grow(
    staff_client: Client, django_assert_max_num_queries
):
    course = CourseFactory()
    part = CoursePartFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    for order in range(12):
        ContentCollectionItemFactory(
            collection_object=part, child_object=TopicFactory(), order=order
        )
    organisation = OrganisationFactory()
    url = _interface_url(organisation.slug, f"courses/{course.pk}")

    with django_assert_max_num_queries(60):
        assert staff_client.get(url).status_code == 200


def _content_action_url(
    organisation: Organisation, course: CourseModel, action: str
) -> str:
    return _interface_url(
        organisation.slug, f"courses/{course.pk}/__panels/content/__actions/{action}"
    )


def _preview_url(
    client: Client, organisation: Organisation, course: CourseModel
) -> str:
    """The Preview action's URL as the course page publishes it, without
    the item parameter."""
    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )
    trigger = document.cssselect(
        "section[data-panel='content'] table button[hx-get*='preview_content']"
    )[0]
    return str(trigger.get("hx-get")).split("?")[0]


def _course_with_topic(topic: Model | None = None) -> tuple[CourseModel, Model]:
    course = cast(CourseModel, CourseFactory())
    item = ContentCollectionItemFactory(
        collection_object=course, child_object=topic or TopicFactory(), order=0
    )
    return course, cast(Model, item)


@pytest.mark.django_db
def test_a_topic_row_carries_a_preview_trigger_for_its_collection_item(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, item = _course_with_topic(TopicFactory(title="Intro"))

    html = staff_client.get(
        _interface_url(organisation.slug, f"courses/{course.pk}")
    ).content.decode()
    panel = lxml.html.fromstring(html).cssselect("section[data-panel='content']")[0]

    (trigger,) = panel.cssselect("table button[aria-label='Preview Intro']")
    assert trigger.get("hx-get").endswith(f"/__actions/preview_content?item={item.pk}")
    assert trigger.text_content().strip() == "Preview"
    assert trigger.get("aria-label") == "Preview Intro"
    assert "view_course_item" not in html
    assert reverse("learner_interface:course_detail", args=[course.slug]) not in html


@pytest.mark.django_db
def test_opening_a_topic_preview_renders_it_read_only_in_the_wide_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, item = _course_with_topic(
        TopicFactory(title="Intro", content="Hello **learners**")
    )
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    html = response.content.decode()
    assert response.status_code == 200
    assert 'data-modal-size="wide"' in html
    assert "Intro (Preview)" in html
    assert "Topic" in html
    assert "Nothing here is saved." not in html
    assert "max-w-reading" in html
    assert "<strong>learners</strong>" in html
    assert "<form" not in html
    assert "Mark complete" not in html
    assert "<nav" not in html


@pytest.mark.django_db
def test_the_course_page_loads_katex_before_the_content_components(
    staff_client: Client,
):
    """A previewed equation typesets only when KaTeX is on the page by the
    time the equation component starts."""
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()

    html = staff_client.get(
        _interface_url(organisation.slug, f"courses/{course.pk}")
    ).content.decode()

    assert "content_engine/vendor/katex/katex.min.css" in html
    katex_script = html.index("content_engine/vendor/katex/katex.min.js")
    assert katex_script < html.index("content_engine/js/alpine-components.js")


@pytest.mark.django_db
def test_a_topic_holding_a_content_link_previews(staff_client: Client):
    organisation = OrganisationFactory()
    TopicFactory(file_path="1. welcome/content.md")
    topic = TopicFactory(
        file_path="2. reading/content.md",
        content=(
            'Go back to <c-content-link path="../1. welcome/content.md">'
            "the Welcome topic</c-content-link>."
        ),
    )
    course, item = _course_with_topic(topic)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert "the Welcome topic" in response.content.decode()


@pytest.mark.django_db
def test_opening_a_topic_preview_writes_nothing(staff_client: Client):
    organisation = OrganisationFactory()
    FileFactory(file_path="pic.png", mime_type="image/png")
    FileFactory(file_path="notes.txt")
    topic = TopicFactory(
        content=(
            '<c-picture src="pic.png" alt="A picture"></c-picture>\n\n'
            '<c-file-download src="notes.txt" text="Get notes"></c-file-download>\n'
        )
    )
    course, item = _course_with_topic(topic)
    url = _preview_url(staff_client, organisation, course)
    counted = [
        TopicProgress,
        CourseProgress,
        LearnerCourseRegistration,
        AuditLogEntry,
        FormProgress,
        QuestionAnswer,
    ]
    before = [model.objects.count() for model in counted]

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert "Get notes" in response.content.decode()
    assert [model.objects.count() for model in counted] == before


@pytest.mark.django_db
def test_a_preview_of_another_courses_item_is_a_404(staff_client: Client):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    _other_course, other_item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={other_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_preview_of_an_item_on_another_site_is_a_404(staff_client: Client):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    with site_context(SiteFactory()):
        _other_course, other_item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={other_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_preview_of_a_part_row_is_a_404(staff_client: Client):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    part_item = ContentCollectionItemFactory(
        collection_object=course, child_object=CoursePartFactory(), order=1
    )
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={part_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "item", ["", "not-a-uuid", "6f1c2f0e-3c1b-4a5e-9a57-0d1f6d3a9b11"]
)
def test_a_preview_with_a_missing_or_malformed_item_is_a_404(
    staff_client: Client, item: str
):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_preview_without_the_htmx_header_or_by_post_is_a_404(staff_client: Client):
    organisation = OrganisationFactory()
    course, item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    plain_get = staff_client.get(f"{url}?item={item.pk}")
    post = staff_client.post(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert (plain_get.status_code, post.status_code) == (404, 404)


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["topic", "form"])
def test_the_preview_url_built_for_the_denial_tests_is_the_published_one(
    staff_client: Client, kind: str
):
    organisation = OrganisationFactory()
    course, item = _course_with_topic() if kind == "topic" else _course_with_form()

    url = _content_action_url(organisation, course, "preview_content")
    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert url == _preview_url(staff_client, organisation, course)
    assert response.status_code == 200


@pytest.mark.django_db
def test_a_course_belonging_only_to_another_organisation_cannot_be_previewed(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, item = _course_with_topic()
    course.organisations.add(OrganisationFactory())
    action_url = _content_action_url(organisation, course, "preview_content")

    page = staff_client.get(_interface_url(organisation.slug, f"courses/{course.pk}"))
    action = staff_client.get(f"{action_url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert (page.status_code, action.status_code) == (404, 404)


@pytest.mark.django_db
def test_a_user_with_no_role_in_the_organisation_cannot_preview(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    course, item = _course_with_topic()
    action_url = _content_action_url(organisation, course, "preview_content")

    response = logged_in_client(UserFactory()).get(
        f"{action_url}?item={item.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


QUESTION_TYPES = [
    "multiple_choice",
    "checkboxes",
    "short_text",
    "long_text",
    "number",
    "date",
    "time",
    "email",
    "url",
    "phone",
    "dropdown",
    "file_upload",
]


def _course_with_form(form: Model | None = None) -> tuple[CourseModel, Model]:
    course = cast(CourseModel, CourseFactory())
    item = ContentCollectionItemFactory(
        collection_object=course, child_object=form or FormFactory(), order=0
    )
    return course, cast(Model, item)


@pytest.mark.django_db
def test_opening_a_form_preview_renders_every_question_type_disabled(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    form = FormFactory(title="Intake", content="Tell us **more**")
    page = FormPageFactory(form=form, title="About you")
    for order, question_type in enumerate(QUESTION_TYPES):
        question = FormQuestionFactory(
            form_page=page, type=question_type, order=order, question=f"Q {order}"
        )
        if question_type in {"multiple_choice", "checkboxes", "dropdown"}:
            QuestionOptionFactory(question=question, text="Yes", order=0)
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    html = response.content.decode()
    document = lxml.html.fromstring(html)
    assert response.status_code == 200
    assert "<strong>more</strong>" in html
    assert "About you" in html
    (heading,) = document.cssselect("h2")
    assert heading.text_content().split() == ["Intake", "(Preview)", "Form"]
    controls = document.cssselect("input, textarea, select")
    assert controls
    assert all(control.get("disabled") is not None for control in controls)
    assert "File upload question" in html
    assert "questionFileUpload" not in html
    assert "hx-post" not in html
    assert "<form" not in html
    assert document.cssselect("button[type='submit']") == []


def _three_page_form(title: str = "Survey") -> tuple[Model, Model]:
    """A survey whose second page is shown only on one answer; returns the
    form and that second page."""
    form = FormFactory(title=title, content="Tell us **everything**")
    first = FormPageFactory(form=form, title="First page", order=0)
    gate = FormQuestionFactory(form_page=first, question="Do you smoke?", order=0)
    option = QuestionOptionFactory(question=gate, text="Yes", order=0)
    second = FormPageFactory(
        form=form, title="Second page", order=1, condition_option=option
    )
    FormQuestionFactory(form_page=second, question="How many a day?", order=0)
    FormPageFactory(form=form, title="Third page", order=2)
    return cast(Model, form), cast(Model, second)


@pytest.mark.django_db
def test_a_page_previews_alone_headed_by_its_place_and_its_condition(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    form, second = _three_page_form()
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(
        f"{url}?item={item.pk}&page={second.pk}", HTTP_HX_REQUEST="true"
    )

    html = response.content.decode()
    document = lxml.html.fromstring(html)
    assert response.status_code == 200
    (heading,) = document.cssselect("h2")
    assert heading.text_content().split() == [
        "Second",
        "page",
        "(Preview)",
        "Form",
        "page",
    ]
    assert "Page 2 of 3: Second page" in html
    assert "Shown only if Do you smoke? is answered Yes" in html
    assert "How many a day?" in html
    assert "Do you smoke?" not in html.split("Shown only if")[0]
    assert "Third page" not in html
    assert "<strong>everything</strong>" not in html
    assert "<form" not in html


@pytest.mark.django_db
def test_a_page_condition_names_its_question_as_rendered_text(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    form = FormFactory(title="Survey")
    first = FormPageFactory(form=form, title="First page", order=0)
    gate = FormQuestionFactory(form_page=first, question="**Did you** attend?", order=0)
    option = QuestionOptionFactory(question=gate, text="No", order=0)
    second = FormPageFactory(
        form=form, title="Second page", order=1, condition_option=option
    )
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(
        f"{url}?item={item.pk}&page={second.pk}", HTTP_HX_REQUEST="true"
    )

    (note,) = [
        p
        for p in lxml.html.fromstring(response.content).cssselect("p")
        if p.text_content().startswith("Shown only if")
    ]
    assert " ".join(note.text_content().split()) == (
        "Shown only if Did you attend? is answered No"
    )
    assert note.cssselect("p p") == []


@pytest.mark.django_db
def test_a_multi_page_form_previews_its_start_page(staff_client: Client):
    organisation = OrganisationFactory()
    form, _second = _three_page_form()
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    html = response.content.decode()
    assert response.status_code == 200
    assert "Survey (Preview)" in html
    assert "<strong>everything</strong>" in html
    assert "3 pages" in html
    assert "2 questions" in html
    for absent in ("Do you smoke?", "First page", "Shown only if", "<form", "Start"):
        assert absent not in html


@pytest.mark.django_db
def test_a_page_of_another_form_is_not_found(staff_client: Client):
    organisation = OrganisationFactory()
    form, _second = _three_page_form()
    _other, other_page = _three_page_form(title="Other survey")
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(
        f"{url}?item={item.pk}&page={other_page.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_page_on_a_topic_is_not_found(staff_client: Client):
    organisation = OrganisationFactory()
    _form, page = _three_page_form()
    course, item = _course_with_topic()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(
        f"{url}?item={item.pk}&page={page.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_opening_a_form_preview_writes_nothing(staff_client: Client):
    organisation = OrganisationFactory()
    form = FormFactory()
    page = FormPageFactory(form=form)
    FormQuestionFactory(form_page=page, type="file_upload")
    FormQuestionFactory(form_page=page, type="short_text")
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)
    counted = [
        TopicProgress,
        CourseProgress,
        LearnerCourseRegistration,
        AuditLogEntry,
        FormProgress,
        QuestionAnswer,
    ]
    before = [model.objects.count() for model in counted]

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert [model.objects.count() for model in counted] == before


@pytest.mark.django_db
def test_a_preview_of_another_courses_form_is_a_404(staff_client: Client):
    organisation = OrganisationFactory()
    course, _item = _course_with_form()
    _other_course, other_item = _course_with_form()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={other_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_preview_of_a_form_on_another_site_is_a_404(staff_client: Client):
    organisation = OrganisationFactory()
    course, _item = _course_with_form()
    with site_context(SiteFactory()):
        _other_course, other_item = _course_with_form()
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={other_item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_form_of_a_course_belonging_only_to_another_organisation_cannot_be_previewed(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, item = _course_with_form()
    course.organisations.add(OrganisationFactory())
    action_url = _content_action_url(organisation, course, "preview_content")

    action = staff_client.get(f"{action_url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert action.status_code == 404


@pytest.mark.django_db
def test_a_form_preview_without_the_htmx_header_or_by_post_is_a_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, item = _course_with_form()
    url = _preview_url(staff_client, organisation, course)

    plain_get = staff_client.get(f"{url}?item={item.pk}")
    post = staff_client.post(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert (plain_get.status_code, post.status_code) == (404, 404)


@pytest.mark.django_db
def test_a_user_with_no_role_cannot_preview_a_form(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    course, item = _course_with_form()
    action_url = _content_action_url(organisation, course, "preview_content")

    response = logged_in_client(UserFactory()).get(
        f"{action_url}?item={item.pk}", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


def _marks(document: lxml.html.HtmlElement) -> list[lxml.html.HtmlElement]:
    return [
        mark
        for mark in document.cssselect("span")
        if mark.text_content().strip().startswith("Correct answer")
    ]


@pytest.mark.django_db
def test_a_quiz_preview_marks_exactly_the_correct_options(staff_client: Client):
    organisation = OrganisationFactory()
    form = FormFactory()
    page = FormPageFactory(form=form)
    single = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    QuestionOptionFactory(question=single, text="Single right", correct=True, order=0)
    QuestionOptionFactory(question=single, text="Single wrong", order=1)
    several = FormQuestionFactory(form_page=page, type="checkboxes", order=1)
    QuestionOptionFactory(question=several, text="Box right 1", correct=True, order=0)
    QuestionOptionFactory(question=several, text="Box right 2", correct=True, order=1)
    QuestionOptionFactory(question=several, text="Box wrong", order=2)
    pick = FormQuestionFactory(form_page=page, type="dropdown", order=2)
    QuestionOptionFactory(question=pick, text="Pick right", correct=True, order=0)
    QuestionOptionFactory(question=pick, text="Pick wrong", order=1)
    course, item = _course_with_form(form)
    url = _preview_url(staff_client, organisation, course)

    response = staff_client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content.decode())
    marks = _marks(document)
    assert response.status_code == 200
    assert len(marks) == 4
    assert all(mark.cssselect("svg") for mark in marks)
    labelled = [
        label.text_content()
        for label in document.cssselect("label")
        if label.cssselect("span") and _marks(label)
    ]
    assert len(labelled) == 3
    assert all("wrong" not in text for text in labelled)
    (dropdown_list,) = document.cssselect("ul")
    assert dropdown_list.text_content().split(":")[1].strip() == "Pick right"


def _course_details_preview_url(organisation: Organisation, course: CourseModel) -> str:
    return _content_action_url(organisation, course, "preview_course_details")


@pytest.mark.django_db
def test_the_course_content_table_opens_with_the_course_details_row(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    (panel,) = document.cssselect("section[data-panel='content']")
    assert panel.cssselect("header button") == []
    first_row = _outline_rows(panel)[0]
    assert "Course details" in first_row.text_content()
    (trigger,) = first_row.cssselect("button[hx-get]")
    assert trigger.get("hx-get") == _course_details_preview_url(organisation, course)
    assert trigger.text_content().strip() == "Preview"
    assert trigger.get("aria-label") == "Preview course details page"


@pytest.mark.django_db
def test_opening_the_course_details_preview_renders_the_learner_facing_page(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    course.title = "Intro to Rust"
    course.content = "Learn **ownership**"
    course.learning_outcomes = ["Borrow safely"]
    course.save()

    response = staff_client.get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    html = response.content.decode()
    assert response.status_code == 200
    assert 'data-modal-size="wide"' in html
    assert "Intro to Rust (Preview)" in html
    assert "Course details" in html
    assert "Nothing here is saved." not in html
    assert "About this course" in html
    assert "learn" in html
    assert "Borrow safely" in html
    assert "<strong>ownership</strong>" in html
    assert "1 lesson" in html
    for absent in (
        "Course content",
        "Enrolment",
        "signup-panel",
        "express_interest",
        "<form",
        reverse("learner_interface:course_detail", args=[course.slug]) + "start",
    ):
        assert absent not in html


@pytest.mark.django_db
def test_opening_the_course_details_preview_writes_nothing(staff_client: Client):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    counted = [
        TopicProgress,
        CourseProgress,
        LearnerCourseRegistration,
        AuditLogEntry,
        FormProgress,
        QuestionAnswer,
    ]
    before = [model.objects.count() for model in counted]

    response = staff_client.get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    assert [model.objects.count() for model in counted] == before


@pytest.mark.django_db
def test_the_course_details_preview_without_the_htmx_header_or_by_post_is_a_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    url = _course_details_preview_url(organisation, course)

    plain_get = staff_client.get(url)
    post = staff_client.post(url, HTTP_HX_REQUEST="true")

    assert (plain_get.status_code, post.status_code) == (404, 404)


@pytest.mark.django_db
def test_a_course_belonging_only_to_another_organisation_has_no_details_preview(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()
    course.organisations.add(OrganisationFactory())

    response = staff_client.get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_user_with_no_role_cannot_open_the_course_details_preview(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    course, _item = _course_with_topic()

    response = logged_in_client(UserFactory()).get(
        _course_details_preview_url(organisation, course), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404
