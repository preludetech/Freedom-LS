"""The educator interface's section configs and the pages they render."""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
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
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import record_entry, record_run_summary
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging import (
    SendResult,
    inbox_for,
    unread_conversation_count,
)
from freedom_ls.comms.messaging_policy import MessagingDecision, MessagingRefusal
from freedom_ls.comms.models import Conversation
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.educator_interface.bulk_runs import run_bulk_action
from freedom_ls.educator_interface.events import COHORT_CHANGED
from freedom_ls.educator_interface.learner_import import create_learner_import
from freedom_ls.educator_interface.messaging import ConversationRow
from freedom_ls.educator_interface.tests.interface_walk import (
    WalkedPanel,
    walk_interface,
)
from freedom_ls.educator_interface.views import (
    CohortDataTable,
    ConversationDataTable,
    MessagesConfig,
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
    register_for_course,
)
from freedom_ls.learner_management.models import (
    BulkActionRun,
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerImport,
    OrganisationMember,
    RunStatus,
)
from freedom_ls.learner_management.role_assignment import GrantableRole, assign_role
from freedom_ls.learner_management.utils import register_cohort_for_course
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.reports.tests.helpers import topic_progress
from freedom_ls.role_based_permissions.loader import get_role_config

QUERY_BUDGET = 60


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
        "Educators",
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
    triggers = {button.get("hx-get") for button in header.cssselect("button[hx-get]")}
    assert triggers == {
        f"{page_url}/__actions/edit",
        f"{page_url}/__actions/deactivate",
    }
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


@pytest.mark.django_db
def test_navigation_toggle_shows_a_menu_icon_not_a_panel_chevron(
    staff_client: Client,
):
    """The content header's navigation toggle drew a chevron instead of a menu icon."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (toggle,) = document.cssselect("button[aria-label='Open navigation panel']")
    (icon,) = toggle.cssselect("[role='img']")
    assert icon.get("aria-label") == "menu"


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
    """The organisation root has no page heading of its own, which used to
    leave a phone with no way to open the navigation."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, ""))

    (toggle,) = document.cssselect(
        "#main-content button[aria-label='Open navigation panel']"
    )
    assert toggle.cssselect("[role='img']")


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
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_settings_tab_answers_404_for_a_role_without_change_cohort(
    mock_site_context, logged_in_client, role: str
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, role, cohort)

    response = logged_in_client(educator).get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/settings")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_header_offers_deactivate_on_an_active_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    page_url = _interface_url(organisation.slug, f"cohorts/{cohort.pk}")

    document = _get_document(staff_client, page_url)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    triggers = {button.get("hx-get") for button in header.cssselect("button[hx-get]")}
    assert f"{page_url}/__actions/deactivate" in triggers
    assert f"{page_url}/__actions/reactivate" not in triggers


@pytest.mark.django_db
def test_header_offers_reactivate_on_an_inactive_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, is_active=False)
    page_url = _interface_url(organisation.slug, f"cohorts/{cohort.pk}")

    document = _get_document(staff_client, page_url)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    triggers = {button.get("hx-get") for button in header.cssselect("button[hx-get]")}
    assert f"{page_url}/__actions/reactivate" in triggers
    assert f"{page_url}/__actions/deactivate" not in triggers


@pytest.mark.django_db
def test_course_page_renders_no_action_buttons(staff_client: Client):
    organisation = OrganisationFactory()
    course = CourseFactory()

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    assert header.cssselect("button[hx-get]") == []
    assert document.cssselect("section[data-panel] button[hx-get]") == []


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
def test_cohort_header_shows_the_active_badge(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=True)

    document = _cohort_page(staff_client, cohort)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    assert "Active" in header.text_content().split()


@pytest.mark.django_db
def test_inactive_cohort_header_shows_the_inactive_badge(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)

    document = _cohort_page(staff_client, cohort)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    assert "Inactive" in header.text_content().split()


@pytest.mark.django_db
def test_cohort_header_shows_learner_and_course_counts(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)
    _add_member(cohort)
    _add_member(cohort)
    CohortCourseRegistrationFactory(cohort=cohort)

    document = _cohort_page(staff_client, cohort)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    stats = {
        dl.cssselect("dt")[0].text_content().strip(): dl.cssselect("dd")[0]
        .text_content()
        .strip()
        for dl in header.cssselect("dl")
    }
    assert stats == {"Learners": "3", "Courses": "1"}


@pytest.mark.django_db
def test_cohort_header_refreshes_its_counts_when_the_cohort_changes(
    staff_client: Client,
):
    """The header stats and tab counts stayed stale after a membership change
    because nothing re-fetched them when the cohort-changed event fired."""
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    (refresher,) = document.cssselect("#instance-header [data-header-refresh-events]")
    assert refresher.get("data-header-refresh-events") == COHORT_CHANGED


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


def _educators_url(organisation: Organisation, cohort: Cohort) -> str:
    return _interface_url(
        organisation.slug, f"cohorts/{cohort.pk}/__tabs/overview/__panels/educators"
    )


@pytest.mark.django_db
def test_educators_block_names_each_educator_and_their_role(
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
        logged_in_client(admin),
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}"),
    )

    (card,) = document.cssselect("section[data-panel='educators']")
    text = " ".join(card.text_content().split())
    assert "Ada Lovelace" in text
    assert "Cohort Admin" in text or "Cohort admin" in text


@pytest.mark.django_db
def test_educators_panel_lists_a_person_added_from_the_cohort_page(
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
        _educators_url(organisation, cohort) + "/__actions/add_member",
        {
            "step": "submit",
            "email": "ada@example.com",
            "role": "cohort_viewer",
            "cohorts": [str(cohort.pk)],
            "confirmed": "1",
        },
        HTTP_HX_REQUEST="true",
    )

    document = _get_document(
        client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )
    (card,) = document.cssselect("section[data-panel='educators']")
    assert ada.display_name in card.text_content()


@pytest.mark.django_db
def test_educators_block_shows_an_empty_state_without_educators(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (card,) = document.cssselect("section[data-panel='educators']")
    assert "No educators assigned to this cohort." in card.text_content()


@pytest.mark.django_db
def test_educators_block_is_absent_for_a_cohort_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    client = logged_in_client(educator)

    page = _get_document(
        client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )
    fragment = client.get(_educators_url(organisation, cohort), HTTP_HX_REQUEST="true")

    assert not page.cssselect("section[data-panel='educators']")
    assert fragment.status_code == 404


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


def _unregister_triggers(document: lxml.html.HtmlElement, cohort: Cohort) -> list[str]:
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
def test_the_courses_tab_offers_unregister_only_on_active_registrations(
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
    (trigger,) = set(_unregister_triggers(document, cohort))
    assert trigger.endswith(f"?registration={active.pk}")


@pytest.mark.django_db
def test_an_inactive_cohorts_courses_tab_shows_no_unregister_trigger(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)
    CohortCourseRegistrationFactory(cohort=cohort, is_active=True)

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    assert _unregister_triggers(document, cohort) == []


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
def test_the_learner_page_has_overview_courses_and_history_tabs(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())

    document = _learner_page(staff_client, learner)

    (nav,) = document.cssselect("nav[aria-label='Learner sections']")
    links = nav.cssselect("a")
    assert [link.get("href").rsplit("/", 1)[-1] for link in links] == [
        "overview",
        "courses",
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
def test_the_learner_header_carries_the_status_badge_and_email_subtitle(
    staff_client: Client,
):
    learner = LearnerFactory(
        organisation=OrganisationFactory(), user__email="ada@example.com"
    )

    document = _learner_page(staff_client, learner)

    (title,) = document.cssselect("#instance-title")
    header = title.xpath("ancestor::div[contains(@class, 'justify-between')][1]")[0]
    assert "Active" in header.text_content()
    assert "ada@example.com" in header.text_content()


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
    assert "March 5, 2024" in table.text_content()


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
    assert "educator_interface/partials/audit_history_empty.html" in template_names


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


def _history_rows(document: lxml.html.HtmlElement) -> list[list[str]]:
    return [
        [cell.text_content().strip() for cell in row.cssselect("td")]
        for row in document.cssselect("[data-tab-set] tbody tr")
    ]


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

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [row[3] for row in rows] == ["newer", "older"]


@pytest.mark.django_db
def test_the_history_tab_pages_stably_when_entries_share_a_timestamp(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    when = timezone.now()
    for number in range(26):
        _history_entry(learner, reason=f"entry {number}", created_at=when)

    first = _history_rows(_learner_page(staff_client, learner, "history"))
    second_page = staff_client.get(
        _interface_url(
            learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
        ),
        {"history-page": 2},
    )
    second = _history_rows(lxml.html.fromstring(second_page.content.decode()))

    reasons = [row[3] for row in first + second]
    assert (len(first), len(second), len(set(reasons))) == (25, 1, 26)


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
def test_the_history_tab_shows_the_code_of_an_unregistered_action(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=learner, organisation=learner.organisation, action="widget.exploded"
    )

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert rows[0][2] == "widget.exploded"


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

    (link,) = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert "learners-export=csv" in link.get("href")


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
def members_client(
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


def _grant_member(
    target: Organisation | Cohort, role: str = "organisation_admin", **user_fields: str
) -> None:
    assign_role(UserFactory(superuser=True), UserFactory(**user_fields), role, target)


@pytest.mark.django_db
def test_an_organisation_admin_sees_each_members_name_and_email(members_client):
    organisation = OrganisationFactory()
    _grant_member(
        organisation, first_name="Ada", last_name="Lovelace", email="ada@example.com"
    )
    client = members_client(organisation, "organisation_admin")

    text = _get_document(client, _interface_url(organisation.slug, "members"))

    assert "Ada Lovelace" in text.text_content()
    assert "ada@example.com" in text.text_content()


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_a_cohort_role_holder_sees_no_administration_group(members_client, role):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = members_client(cohort, role)

    document = _get_document(client, _interface_url(organisation.slug, "cohorts"))

    headings = [h.text_content().strip() for h in document.cssselect("#sidebar-nav h2")]
    assert headings == ["Teaching"]


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_members_is_a_404_for_a_cohort_role_holder(members_client, role):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = members_client(cohort, role)

    response = client.get(_interface_url(organisation.slug, "members"))

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
        _interface_url(organisation.slug, "members")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_nameless_member_shows_the_email_alone(members_client):
    organisation = OrganisationFactory()
    _grant_member(organisation, first_name="", last_name="", email="bare@example.com")
    client = members_client(organisation, "organisation_admin")

    document = _get_document(client, _interface_url(organisation.slug, "members"))

    names = [
        e.text_content() for e in document.cssselect("#main-content span.truncate")
    ]
    assert "bare@example.com" in names
    assert not document.cssselect("#main-content span.truncate.text-muted")


@pytest.mark.django_db
def test_a_member_path_with_an_id_under_it_is_a_404(members_client):
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")

    response = client.get(_interface_url(organisation.slug, f"members/{uuid.uuid4()}"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_member_name_is_escaped(members_client):
    organisation = OrganisationFactory()
    _grant_member(organisation, first_name="<b>x</b>")
    client = members_client(organisation, "organisation_admin")

    response = client.get(_interface_url(organisation.slug, "members"))

    assert "&lt;b&gt;x&lt;/b&gt;" in response.content.decode()
    assert "<b>x</b>" not in response.content.decode()


def _members_document(client: Client, organisation: Organisation):
    return _get_document(client, _interface_url(organisation.slug, "members"))


def _member_row(document, email: str):
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
QUERY_BOUND = 54


MARKERS = {"You", "Inactive", "Account turned off", "Also a learner"}


def _marker_labels(row) -> set[str]:
    return {e.text_content().strip() for e in row.cssselect("span")} & MARKERS


def _hold(user, role: str, target, grantor=None) -> None:
    assign_role(grantor or UserFactory(superuser=True), user, role, target)


@pytest.mark.django_db
def test_an_organisation_admins_roles_cell_reads_whole_organisation(members_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="boss@example.com"), "organisation_admin", organisation)
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "boss@example.com")

    assert _scope_lines(row) == ["Whole organisation"]
    assert "Organisation admin" in row.text_content()


@pytest.mark.django_db
def test_two_cohorts_read_both_names(members_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="two@example.com")
    for name in ("Alpha", "Bravo"):
        _hold(user, "cohort_admin", CohortFactory(organisation=organisation, name=name))
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "two@example.com")

    assert _scope_lines(row) == ["Alpha, Bravo"]


@pytest.mark.django_db
def test_four_cohorts_read_two_names_and_the_rest_as_a_count(members_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="four@example.com")
    for name in ("Alpha", "Bravo", "Charlie", "Delta"):
        _hold(
            user, "cohort_viewer", CohortFactory(organisation=organisation, name=name)
        )
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "four@example.com")

    (scope,) = row.cssselect("ul li span[title]")
    assert scope.text_content().strip() == "Alpha, Bravo +2 more"
    assert scope.get("title") == "Alpha, Bravo, Charlie, Delta"


@pytest.mark.django_db
def test_an_inactive_cohort_carries_the_inactive_marker(members_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Old", is_active=False)
    _hold(UserFactory(email="old@example.com"), "cohort_viewer", cohort)
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "old@example.com")

    assert _scope_lines(row) == ["Old (inactive)"]


@pytest.mark.django_db
def test_a_role_names_who_added_it(members_client):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True, first_name="Grace", last_name="Hopper")
    _hold(
        UserFactory(email="added@example.com"),
        "organisation_admin",
        organisation,
        grantor,
    )
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "added@example.com")

    assert "by Grace Hopper" in row.text_content()


@pytest.mark.django_db
def test_a_role_with_no_recorded_grantor_reads_not_recorded(members_client):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True)
    _hold(
        UserFactory(email="orphan@example.com"),
        "organisation_admin",
        organisation,
        grantor,
    )
    grantor.delete()
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "orphan@example.com")

    assert "by Not recorded" in row.text_content()


def _make_viewer_and_subject(members_client, organisation, case: str):
    """Returns (client, email of the row to inspect) for a marker case."""
    subject = UserFactory(email="subject@example.com")
    _hold(subject, "cohort_viewer", CohortFactory(organisation=organisation))
    viewer_client = members_client(organisation, "organisation_admin")
    if case == "suspended":
        OrganisationMember.objects.filter(user=subject).update(is_active=False)
    elif case == "turned_off":
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
        ("suspended", {"Inactive"}),
        ("turned_off", {"Account turned off"}),
        ("learner", {"Also a learner"}),
        ("inactive_learner", set()),
    ],
)
def test_each_marker_appears_for_its_case_only(members_client, case, expected):
    organisation = OrganisationFactory()
    client = _make_viewer_and_subject(members_client, organisation, case)

    row = _member_row(_members_document(client, organisation), "subject@example.com")

    assert _marker_labels(row) == expected


@pytest.mark.django_db
def test_the_viewers_own_row_is_marked_you(members_client):
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")
    document = _members_document(client, organisation)

    (row,) = document.cssselect("#main-content tbody tr")

    assert _marker_labels(row) == {"You"}


@pytest.mark.django_db
def test_a_member_with_no_organisation_member_row_is_suspended(members_client):
    organisation = OrganisationFactory()
    subject = UserFactory(email="subject@example.com")
    _hold(subject, "organisation_admin", organisation)
    OrganisationMember.objects.filter(user=subject).delete()
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "subject@example.com")

    assert _marker_labels(row) == {"Inactive"}


@pytest.mark.django_db
def test_a_superuser_holding_one_cohort_role_shows_that_role_only(members_client):
    organisation = OrganisationFactory()
    superuser = UserFactory(superuser=True, email="super@example.com")
    _hold(superuser, "cohort_viewer", CohortFactory(organisation=organisation))
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "super@example.com")

    assert len(row.cssselect("ul li")) == 1
    assert "Cohort viewer" in row.text_content()


@pytest.mark.django_db
def test_a_cohort_name_is_escaped_in_the_scope(members_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="<i>x</i>")
    _hold(UserFactory(), "cohort_viewer", cohort)
    client = members_client(organisation, "organisation_admin")

    content = client.get(_interface_url(organisation.slug, "members")).content.decode()

    assert "&lt;i&gt;x&lt;/i&gt;" in content
    assert "<i>x</i>" not in content


@pytest.mark.django_db
def test_a_full_page_of_members_stays_within_a_fixed_query_bound(
    members_client, django_assert_max_num_queries
):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True)
    for _ in range(10):
        user = UserFactory()
        _hold(user, "organisation_admin", organisation, grantor)
        _hold(user, "cohort_viewer", CohortFactory(organisation=organisation), grantor)
        LearnerFactory(user=user, organisation=organisation)
    client = members_client(organisation, "organisation_admin")
    url = _interface_url(organisation.slug, "members")

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
        client, _interface_url(organisation.slug, "members") + f"?members-q={term}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "term", ["Wanjiru", "Kamau", "wanjiru.k@"], ids=["first", "last", "email"]
)
def test_members_search_matches_first_name_last_name_and_email(members_client, term):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(first_name="Wanjiru", last_name="Kamau", email="wanjiru.k@x.org"),
        "organisation_admin",
        organisation,
    )
    _hold(UserFactory(email="other@x.org"), "organisation_admin", organisation)
    client = members_client(organisation, "organisation_admin")

    document = _members_search(client, organisation, term)

    (row,) = document.cssselect("#main-content tbody tr")
    assert "wanjiru.k@x.org" in row.text_content()


@pytest.mark.django_db
def test_the_role_filter_narrows_the_members_page(members_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    _hold(UserFactory(email="viewer@x.org"), "cohort_viewer", cohort)
    client = members_client(organisation, "organisation_admin")

    document = _get_document(
        client,
        _interface_url(organisation.slug, "members") + "?members-role=cohort_viewer",
    )

    (row,) = document.cssselect("#main-content tbody tr")
    assert "viewer@x.org" in row.text_content()


@pytest.mark.django_db
def test_picking_a_role_from_the_default_drops_all_roles_from_its_link(members_client):
    """From the default "All roles" state, a role's choice link selected only
    that role instead of keeping "All roles" beside it."""
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")

    document = _members_document(client, organisation)

    (link,) = [
        a
        for a in document.cssselect("details a")
        if a.text_content().strip() == "Cohort admin"
    ]
    assert link.get("href").endswith("?members-role=cohort_admin")


@pytest.mark.django_db
def test_the_mobile_role_select_has_a_single_all_roles_option(members_client):
    """The mobile Role select listed both a blank "All" and "All roles"."""
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")

    document = _members_document(client, organisation)

    (select,) = document.cssselect("select[name=members-role]")
    labels = [o.text_content().strip() for o in select.cssselect("option")]
    assert labels[:2] == ["All roles", "Organisation admin"]


@pytest.mark.django_db
def test_the_help_paragraph_carries_each_role_description(members_client):
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")
    config = get_role_config(organisation.site.name)

    text = (
        _members_document(client, organisation)
        .cssselect("#main-content")[0]
        .text_content()
    )

    assert "Members are the people who help run this organisation" in text
    assert all(
        f"{config[role].display_name}: {config[role].description}" in text
        for role in ("organisation_admin", "cohort_admin", "cohort_viewer")
    )


ONLY_MEMBER_LINE = "You're the only member here."


@pytest.mark.django_db
def test_a_lone_organisation_admin_is_told_they_are_the_only_member(members_client):
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")

    text = _members_document(client, organisation).text_content()

    assert ONLY_MEMBER_LINE in text


@pytest.mark.django_db
def test_the_only_member_line_goes_once_a_second_member_exists(members_client):
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")
    _hold(UserFactory(), "organisation_admin", organisation)

    text = _members_document(client, organisation).text_content()

    assert ONLY_MEMBER_LINE not in text


@pytest.mark.django_db
def test_the_member_header_first_links_to_descending_first_name(members_client):
    """The list already arrives by first name, so the first click flips it."""
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")

    document = _get_document(client, _interface_url(organisation.slug, "members"))

    (link,) = document.xpath("//thead//a[normalize-space()='Member']")
    assert "members-sort=-first_name" in link.get("href")


@pytest.mark.django_db
def test_a_search_with_no_match_says_so_and_offers_to_clear_filters(members_client):
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")

    document = _members_search(client, organisation, "nobody-has-this-name")

    (cell,) = document.cssselect("#main-content tbody td")
    (link,) = cell.cssselect("a")
    assert cell.text_content().split("Clear filters")[0].strip() == "No members match."
    assert "members-q" not in link.get("href")


@pytest.mark.django_db
def test_a_filter_with_no_match_says_so(members_client):
    organisation = OrganisationFactory()
    client = members_client(organisation, "organisation_admin")

    document = _get_document(
        client,
        _interface_url(organisation.slug, "members") + "?members-role=cohort_viewer",
    )

    (cell,) = document.cssselect("#main-content tbody td")
    assert "No members match." in cell.text_content()


@pytest.mark.django_db
def test_an_organisation_with_no_members_says_so(mock_site_context, logged_in_client):
    organisation = OrganisationFactory()
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", mock_site_context
    )

    document = _members_document(logged_in_client(site_admin), organisation)

    (cell,) = document.cssselect("#main-content tbody td")
    assert "No members in this organisation yet." in cell.text_content()
    assert "Add member" in cell.text_content()


@pytest.mark.django_db
def test_the_educators_panel_refreshes_on_member_changes(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (card,) = document.cssselect("section[data-panel='educators']")
    assert "memberChanged" in lxml.html.tostring(card).decode()


@pytest.mark.django_db
def test_the_cohort_history_panel_refreshes_on_member_changes(staff_client: Client):
    """Adding an educator from the Educators panel writes a role.assigned
    entry with the cohort as subject and answers with memberChanged alone."""
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(
        staff_client,
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history"),
    )

    (card,) = document.cssselect("section[data-panel='history']")
    assert "memberChanged from:body" in card.get("hx-trigger")


def _remove_triggers(row) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if "deactivate_role" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_the_viewers_own_row_has_no_trigger_and_says_why(members_client):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True, email="me@example.com")
    assign_role(UserFactory(superuser=True), viewer, "organisation_admin", organisation)
    client = Client()
    client.force_login(viewer)

    row = _member_row(_members_document(client, organisation), "me@example.com")

    assert row.cssselect("button[hx-get]") == []
    assert row.cssselect("[aria-label='Locked']")
    assert "You can't change your own roles. Ask another organisation admin." in (
        " ".join(row.text_content().split())
    )


@pytest.mark.django_db
def test_another_members_entry_offers_remove_to_an_organisation_admin(members_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    cohort = CohortFactory(organisation=organisation)
    _hold(user, "cohort_viewer", cohort)
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "other@example.com")

    (trigger,) = _remove_triggers(row)
    assert f"user={user.pk}&role=cohort_viewer" in trigger


def _change_cohorts_triggers(row) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if "change_cohorts" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_a_cohort_role_entry_offers_change_cohorts(members_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "other@example.com")

    (trigger,) = _change_cohorts_triggers(row)
    assert f"user={user.pk}&role=cohort_viewer" in trigger


@pytest.mark.django_db
def test_an_organisation_admin_entry_offers_no_change_cohorts(members_client):
    organisation = OrganisationFactory()
    _hold(UserFactory(email="boss@example.com"), "organisation_admin", organisation)
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "boss@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_a_role_the_viewer_may_not_give_has_no_change_cohorts(
    members_client, monkeypatch
):
    organisation = OrganisationFactory()
    _hold(
        UserFactory(email="other@example.com"),
        "cohort_viewer",
        CohortFactory(organisation=organisation),
    )
    client = members_client(organisation, "organisation_admin")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("organisation_admin", None)],
    )

    row = _member_row(_members_document(client, organisation), "other@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_a_turned_off_accounts_row_has_no_change_cohorts(members_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="off@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    User.objects.filter(pk=user.pk).update(is_active=False)
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "off@example.com")

    assert _change_cohorts_triggers(row) == []


@pytest.mark.django_db
def test_an_entry_the_viewer_may_not_revoke_has_no_remove(members_client, monkeypatch):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    _hold(UserFactory(email="other@example.com"), "cohort_viewer", cohort)
    client = members_client(organisation, "organisation_admin")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("organisation_admin", None)],
    )

    row = _member_row(_members_document(client, organisation), "other@example.com")

    assert _remove_triggers(row) == []


@pytest.mark.django_db
def test_a_turned_off_accounts_row_offers_remove_and_nothing_else(members_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="off@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    User.objects.filter(pk=user.pk).update(is_active=False)
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "off@example.com")

    assert len(row.cssselect("button[hx-get]")) == 1
    assert len(_remove_triggers(row)) == 1


def _state_triggers(row, action: str) -> list[str]:
    return [
        button.get("hx-get")
        for button in row.cssselect("button[hx-get]")
        if f"__actions/{action}?" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_an_active_member_row_offers_deactivate_and_not_reactivate(members_client):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "other@example.com")

    (trigger,) = _state_triggers(row, "deactivate")
    assert f"user={user.pk}" in trigger
    assert _state_triggers(row, "reactivate") == []


@pytest.mark.django_db
@pytest.mark.parametrize("row_state", ["inactive", "missing"])
def test_an_inactive_member_row_offers_reactivate_and_not_deactivate(
    members_client, row_state
):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    members = OrganisationMember.objects.filter(user=user)
    if row_state == "inactive":
        members.update(is_active=False)
    else:
        members.delete()
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "other@example.com")

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
    members_client, prepare
):
    organisation = OrganisationFactory()
    user = UserFactory(email="other@example.com")
    _hold(user, "cohort_viewer", CohortFactory(organisation=organisation))
    prepare(user, organisation)
    client = members_client(organisation, "organisation_admin")

    row = _member_row(_members_document(client, organisation), "other@example.com")

    assert _state_triggers(row, "deactivate") == []
    assert _state_triggers(row, "reactivate") == []


@pytest.mark.django_db
def test_the_viewers_own_row_offers_neither_state_action(members_client):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True, email="me@example.com")
    assign_role(UserFactory(superuser=True), viewer, "organisation_admin", organisation)
    client = Client()
    client.force_login(viewer)

    row = _member_row(_members_document(client, organisation), "me@example.com")

    assert _state_triggers(row, "deactivate") == []
    assert _state_triggers(row, "reactivate") == []


# The Messages section: the educator's own conversations with learners of the
# organisation, and the thread page each one opens.


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


def _msg_url(organisation: Organisation, path_string: str = "messages") -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
    )


@pytest.fixture
def msg_client_for(logged_in_client):
    return lambda user: cast(Client, logged_in_client(user))


@pytest.mark.django_db
@messages_section
def test_the_list_shows_the_educators_conversation_with_a_learner_and_links_to_it(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(educator, _msg_learner(organisation).user)

    response = msg_client_for(educator).get(_msg_url(organisation))

    assert response.status_code == 200
    page = lxml.html.fromstring(response.content.decode())
    links = page.xpath(
        f"//a[@href='{_msg_url(organisation, f'messages/{conversation.pk}')}']"
    )
    assert links
    assert "Ada Lovelace" in links[0].text_content()


@pytest.mark.django_db
@messages_section
def test_the_list_leaves_out_a_colleagues_conversation_and_a_foreign_learners(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    _msg_conversation(educator, _msg_learner(organisation).user)
    _msg_conversation(
        _msg_educator(organisation),
        _msg_learner(organisation, first_name="Colleague", last_name="Pupil").user,
    )
    _msg_conversation(
        educator,
        _msg_learner(
            OrganisationFactory(), first_name="Foreign", last_name="Pupil"
        ).user,
    )

    content = msg_client_for(educator).get(_msg_url(organisation)).content.decode()

    assert "Ada Lovelace" in content
    assert "Colleague" not in content
    assert "Foreign" not in content


@pytest.mark.django_db
@messages_section
def test_a_site_admin_sees_only_their_own_conversations(
    msg_client_for, mock_site_context
):
    organisation = OrganisationFactory()
    learner = _msg_learner(organisation)
    site_admin = cast(User, UserFactory(staff=True))
    _grant(site_admin, "site_admin", mock_site_context)
    _msg_conversation(_msg_educator(organisation), learner.user)
    mine = _msg_conversation(
        site_admin,
        _msg_learner(organisation, first_name="Grace", last_name="Hopper").user,
    )

    content = msg_client_for(site_admin).get(_msg_url(organisation)).content.decode()

    assert str(mine.pk) in content
    assert "Grace Hopper" in content
    assert "Ada Lovelace" not in content


@pytest.mark.django_db
@messages_section
def test_the_status_column_shows_the_unread_marker(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)
    conversation = _msg_conversation(educator, learner.user)
    MessageFactory(conversation=conversation, sender=learner.user)

    content = msg_client_for(educator).get(_msg_url(organisation)).content.decode()

    assert "Unread" in content


@pytest.mark.django_db
@messages_section
def test_the_status_column_shows_read_only_when_the_policy_refuses_a_reply(
    msg_client_for, monkeypatch
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(educator, _msg_learner(organisation).user)
    monkeypatch.setattr(
        "freedom_ls.educator_interface.views.reply_decisions",
        lambda *, viewer, conversations: {
            c.pk: MessagingDecision.refuse(MessagingRefusal.NO_RELATIONSHIP)
            for c in conversations
        },
    )

    content = msg_client_for(educator).get(_msg_url(organisation)).content.decode()

    assert str(conversation.pk) in content
    assert "Read only" in content


@pytest.mark.django_db
@messages_section
def test_the_lists_query_count_does_not_grow_with_the_rows(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    client = msg_client_for(educator)
    for _ in range(2):
        _msg_conversation(educator, _msg_learner(organisation).user)
    client.get(_msg_url(organisation))

    with CaptureQueriesContext(connection) as few:
        assert client.get(_msg_url(organisation)).status_code == 200

    for _ in range(6):
        _msg_conversation(educator, _msg_learner(organisation).user)
    with CaptureQueriesContext(connection) as many:
        assert client.get(_msg_url(organisation)).status_code == 200

    assert len(many) == len(few)


@pytest.mark.django_db
@messages_section
def test_the_table_names_a_row_by_the_msg_learner():
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(educator, _msg_learner(organisation).user)
    row = ConversationRow(
        conversation=inbox_for(educator).get(pk=conversation.pk),
        other=conversation.participants.exclude(user=educator).get().user,
        can_reply=True,
    )

    assert ConversationDataTable.get_row_label(row) == "Ada Lovelace"


@pytest.mark.django_db
@messages_section
def test_the_thread_page_carries_the_back_control_and_posts_to_send(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(educator, _msg_learner(organisation).user)

    response = msg_client_for(educator).get(
        _msg_url(organisation, f"messages/{conversation.pk}")
    )

    assert response.status_code == 200
    page = lxml.html.fromstring(response.content.decode())
    back = page.xpath("//a[@aria-label='Back to messages']")
    assert back
    assert back[0].get("href") == _msg_url(organisation)
    send_url = reverse("conversations:send", kwargs={"pk": conversation.pk})
    assert page.xpath(f"//form[@hx-post='{send_url}']")
    assert page.xpath("//*[@id='thread-cursor']")
    assert page.xpath("//*[@id='composer']")


@pytest.mark.django_db
@messages_section
def test_the_thread_header_names_the_learner_as_a_second_level_heading(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(educator, _msg_learner(organisation).user)

    content = (
        msg_client_for(educator)
        .get(_msg_url(organisation, f"messages/{conversation.pk}"))
        .content.decode()
    )

    page = lxml.html.fromstring(content)
    pane = page.xpath("//section[@x-data='conversationThread']")[0]
    assert [h.text_content().strip() for h in pane.xpath(".//h2")] == ["Ada Lovelace"]
    assert not pane.xpath(".//h1")


@pytest.mark.django_db
@messages_section
def test_opening_the_thread_marks_it_read(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)
    conversation = _msg_conversation(educator, learner.user)
    MessageFactory(conversation=conversation, sender=learner.user)
    assert unread_conversation_count(educator) == 1

    msg_client_for(educator).get(_msg_url(organisation, f"messages/{conversation.pk}"))

    assert unread_conversation_count(educator) == 0


@pytest.mark.django_db
@messages_section
def test_opening_an_unread_thread_asks_the_page_to_refresh_its_counts(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)
    conversation = _msg_conversation(educator, learner.user)
    MessageFactory(conversation=conversation, sender=learner.user)
    client = msg_client_for(educator)
    url = _msg_url(organisation, f"messages/{conversation.pk}")

    first = lxml.html.fromstring(client.get(url, HTTP_HX_REQUEST="true").content)
    again = lxml.html.fromstring(client.get(url, HTTP_HX_REQUEST="true").content)

    assert first.xpath("//section[@data-just-read]")
    assert not again.xpath("//section[@data-just-read]")


@pytest.mark.django_db
@messages_section
def test_a_conversation_with_a_learner_of_another_organisation_is_a_404(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(educator, _msg_learner(OrganisationFactory()).user)

    response = msg_client_for(educator).get(
        _msg_url(organisation, f"messages/{conversation.pk}")
    )

    assert response.status_code == 404


@pytest.mark.django_db
@messages_section
def test_a_colleagues_conversation_is_a_404(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(
        _msg_educator(organisation), _msg_learner(organisation).user
    )

    response = msg_client_for(educator).get(
        _msg_url(organisation, f"messages/{conversation.pk}")
    )

    assert response.status_code == 404


@pytest.mark.django_db
@messages_section
def test_a_conversation_whose_learner_was_deleted_leaves_the_list_and_404s(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    gone = _msg_learner(organisation, first_name="Gone", last_name="Soon")
    conversation = _msg_conversation(educator, gone.user)
    _msg_conversation(educator, _msg_learner(organisation).user)
    gone.user.delete()
    client = msg_client_for(educator)

    listing = client.get(_msg_url(organisation)).content.decode()
    thread = client.get(_msg_url(organisation, f"messages/{conversation.pk}"))

    assert "Ada Lovelace" in listing
    assert "Gone Soon" not in listing
    assert thread.status_code == 404


@pytest.mark.django_db
@messages_section
def test_messaging_off_hides_the_nav_item_and_404s_the_paths(msg_client_for, settings):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(educator, _msg_learner(organisation).user)
    client = msg_client_for(educator)
    assert "aria-current" in client.get(_msg_url(organisation)).content.decode()

    settings.MESSAGING_ENABLED = False

    dashboard = client.get(_msg_url(organisation, "dashboard")).content.decode()
    assert f'href="{_msg_url(organisation)}"' not in dashboard
    assert client.get(_msg_url(organisation)).status_code == 404
    assert (
        client.get(_msg_url(organisation, f"messages/{conversation.pk}")).status_code
        == 404
    )


@pytest.mark.django_db
@messages_section
def test_the_messages_nav_item_is_listed_when_messaging_is_on(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)

    dashboard = (
        msg_client_for(educator)
        .get(_msg_url(organisation, "dashboard"))
        .content.decode()
    )

    assert f'href="{_msg_url(organisation)}"' in dashboard


@pytest.mark.django_db
@messages_section
def test_the_section_is_available_only_while_messaging_is_on(settings):
    settings.MESSAGING_ENABLED = True
    request = RequestFactory().get("/")
    assert MessagesConfig.is_available(request) is True
    settings.MESSAGING_ENABLED = False
    assert MessagesConfig.is_available(request) is False


def _count_url(organisation: Organisation) -> str:
    return reverse(
        "educator_interface:messages_unread_count",
        kwargs={"organisation_slug": organisation.slug},
    )


@pytest.mark.django_db
@messages_section
def test_the_count_view_counts_unread_conversations_of_the_organisation(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    for _ in range(2):
        learner = _msg_learner(organisation)
        MessageFactory(
            conversation=_msg_conversation(educator, learner.user),
            sender=learner.user,
        )
    read_learner = _msg_learner(organisation)
    _msg_conversation(educator, read_learner.user)
    foreign_learner = _msg_learner(OrganisationFactory())
    MessageFactory(
        conversation=_msg_conversation(educator, foreign_learner.user),
        sender=foreign_learner.user,
    )

    response = msg_client_for(educator).get(_count_url(organisation))

    assert response.status_code == 200
    assert response.content.decode().strip() == "2"


@pytest.mark.django_db
@messages_section
def test_an_anonymous_htmx_count_poll_is_sent_to_login(client):
    organisation = OrganisationFactory()

    response = client.get(_count_url(organisation), HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert "HX-Redirect" in response


@pytest.mark.django_db
@messages_section
def test_the_count_view_is_empty_when_nothing_is_unread(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    _msg_conversation(educator, _msg_learner(organisation).user)

    response = msg_client_for(educator).get(_count_url(organisation))

    assert response.status_code == 200
    assert response.content.decode().strip() == ""


@pytest.mark.django_db
@messages_section
def test_the_count_view_caps_a_large_count(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    for _ in range(100):
        learner = _msg_learner(organisation)
        MessageFactory(
            conversation=_msg_conversation(educator, learner.user),
            sender=learner.user,
        )

    response = msg_client_for(educator).get(_count_url(organisation))

    assert response.content.decode().strip() == "99+"


@pytest.mark.django_db
@messages_section
def test_the_count_view_404s_for_an_inaccessible_organisation(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)

    response = msg_client_for(educator).get(_count_url(OrganisationFactory()))

    assert response.status_code == 404


@pytest.mark.django_db
@messages_section
def test_the_count_view_404s_when_messaging_is_off(msg_client_for, settings):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    settings.MESSAGING_ENABLED = False

    response = msg_client_for(educator).get(_count_url(organisation))

    assert response.status_code == 404


@pytest.mark.django_db
@messages_section
def test_rendering_the_interface_runs_no_unread_count_query(
    msg_client_for, monkeypatch
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)

    def _fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("the unread count was queried during navigation")

    monkeypatch.setattr(
        "freedom_ls.educator_interface.views.conversations_in_organisation", _fail
    )

    response = msg_client_for(educator).get(_msg_url(organisation, "dashboard"))

    assert response.status_code == 200


@pytest.mark.django_db
@messages_section
def test_the_sidebar_carries_a_preserved_self_polling_count_fragment(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)

    page = lxml.html.fromstring(
        msg_client_for(educator)
        .get(_msg_url(organisation, "dashboard"))
        .content.decode()
    )

    [span] = page.xpath(f"//*[@id='menu-count-messages-{organisation.slug}']")
    assert span.get("hx-preserve") is not None
    assert span.get("hx-get") == _count_url(organisation)
    assert span.get("hx-push-url") == "false"
    assert span.get("x-data") == "refreshTimer"
    assert span.get("data-poll-seconds") == "45"
    assert "conversationChanged from:body" in span.get("hx-trigger")


@pytest.mark.django_db
@messages_section
def test_a_section_without_a_count_url_renders_no_count_fragment(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)

    page = lxml.html.fromstring(
        msg_client_for(educator)
        .get(_msg_url(organisation, "dashboard"))
        .content.decode()
    )

    ids = page.xpath("//*[starts-with(@id, 'menu-count-')]/@id")
    assert ids == [f"menu-count-messages-{organisation.slug}"]


def _new_message_url(organisation: Organisation, **query: str) -> str:
    base = _msg_url(organisation, "messages/__actions/new_message")
    if not query:
        return base
    return base + "?" + "&".join(f"{key}={value}" for key, value in query.items())


def _cohort_learner(organisation: Organisation, cohort: Cohort, **user_fields: str):
    learner = _msg_learner(organisation, **user_fields)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner


@pytest.mark.django_db
@messages_section
def test_the_messages_list_offers_the_new_message_action(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)

    content = msg_client_for(educator).get(_msg_url(organisation)).content.decode()

    assert 'hx-get="' + _new_message_url(organisation) + '"' in content
    assert "New message" in content


@pytest.mark.django_db
@messages_section
def test_the_thread_page_offers_the_new_message_action(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    conversation = _msg_conversation(educator, _msg_learner(organisation).user)

    content = (
        msg_client_for(educator)
        .get(_msg_url(organisation, f"messages/{conversation.pk}"))
        .content.decode()
    )

    action_url = _msg_url(
        organisation, f"messages/{conversation.pk}/__actions/new_message"
    )
    assert f'hx-get="{action_url}"' in content


@pytest.mark.django_db
@messages_section
def test_new_message_groups_visible_learners_under_cohort_headings_with_emails(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    cohort = CohortFactory(organisation=organisation, name="Autumn intake")
    learner = _cohort_learner(
        organisation, cohort, first_name="Kaia", email="kaia@example.com"
    )

    response = msg_client_for(educator).get(_new_message_url(organisation, q="ka"))

    assert response.status_code == 200
    page = lxml.html.fromstring(response.content.decode())
    assert page.xpath("//h2[@id='app-modal-title']")[0].text_content() == "New message"
    headings = [
        h.text_content().strip()
        for h in page.xpath("//h2[contains(@id, 'recipient-group')]")
    ]
    assert headings == ["Autumn intake"]
    row = page.xpath("//*[@id='recipient-results']//li")[0]
    assert "Kaia" in row.text_content()
    assert "kaia@example.com" in row.text_content()
    link = row.xpath(".//a")[0]
    assert link.get("hx-get") == _new_message_url(
        organisation, recipient=str(learner.user.pk)
    )
    assert link.get("hx-target") == "#app-modal-body"


@pytest.mark.django_db
@messages_section
def test_new_message_search_field_is_labelled_to_and_selects_the_results(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)

    content = (
        msg_client_for(educator).get(_new_message_url(organisation)).content.decode()
    )
    page = lxml.html.fromstring(content)

    assert page.xpath("//label[normalize-space()='To']")
    form = page.xpath("//form[@id='recipient-search']")[0]
    assert form.get("hx-get") == _new_message_url(organisation)
    assert form.get("hx-target") == "#recipient-results"
    assert form.get("hx-select") == "#recipient-results"


@pytest.mark.django_db
@messages_section
def test_new_message_focuses_the_to_search_field(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)

    content = (
        msg_client_for(educator).get(_new_message_url(organisation)).content.decode()
    )

    page = lxml.html.fromstring(content)
    assert [el.get("id") for el in page.xpath("//*[@autofocus]")] == ["recipient-q"]


@pytest.mark.django_db
@messages_section
def test_new_message_with_a_recipient_focuses_the_message_box(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)

    content = (
        msg_client_for(educator)
        .get(_new_message_url(organisation, recipient=str(learner.user.pk)))
        .content.decode()
    )

    page = lxml.html.fromstring(content)
    assert [el.get("id") for el in page.xpath("//*[@autofocus]")] == ["message-body"]


@pytest.mark.django_db
@messages_section
def test_new_message_never_lists_a_learner_of_another_organisation(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    foreign = _msg_learner(
        OrganisationFactory(), first_name="Zelda", last_name="Foreign"
    )
    _msg_learner(organisation, first_name="Zed", last_name="Local")

    content = (
        msg_client_for(educator)
        .get(_new_message_url(organisation, q="Ze"))
        .content.decode()
    )

    assert "Zed Local" in content
    assert "Zelda" not in content
    response = msg_client_for(educator).get(
        _new_message_url(organisation, recipient=str(foreign.user.pk))
    )
    assert response.status_code == 404


@pytest.mark.django_db
@messages_section
def test_new_message_no_match_reads_the_same_as_an_unreachable_name(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    _msg_learner(OrganisationFactory(), first_name="Zelda", last_name="Foreign")
    client = msg_client_for(educator)

    absent = client.get(_new_message_url(organisation, q="Nobody")).content.decode()
    refused = client.get(_new_message_url(organisation, q="Zelda")).content.decode()

    assert "No one you can message matches" in absent
    assert absent.replace("Nobody", "X") == refused.replace("Zelda", "X")


@pytest.mark.django_db
@messages_section
def test_new_message_with_a_recipient_shows_to_name_and_the_composer(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)

    response = msg_client_for(educator).get(
        _new_message_url(organisation, recipient=str(learner.user.pk))
    )

    page = lxml.html.fromstring(response.content.decode())
    assert "To Ada Lovelace" in " ".join(page.text_content().split())
    assert page.xpath("//a[normalize-space()='Change']")
    composer = page.xpath("//form[@id='composer']")[0]
    assert composer.get("hx-post") == _new_message_url(organisation)
    assert composer.get("hx-target") == "#app-modal-body"
    assert page.xpath("//input[@name='recipient']")[0].get("value") == str(
        learner.user.pk
    )


@pytest.mark.django_db
@messages_section
def test_posting_a_new_message_creates_the_conversation_and_navigates_to_it(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)

    response = msg_client_for(educator).post(
        _new_message_url(organisation),
        {
            "recipient": learner.user.pk,
            "body": "Welcome aboard",
            "client_key": str(uuid4()),
        },
    )

    conversation = inbox_for(educator).get()
    assert response.status_code == 204
    location = json.loads(response["HX-Location"])
    assert location["path"] == _msg_url(organisation, f"messages/{conversation.pk}")
    assert location["target"] == "#main-content"
    assert "closeModal" in response["HX-Trigger"]


@pytest.mark.django_db
@messages_section
def test_posting_a_refused_new_message_returns_the_modal_at_422_with_the_draft(
    msg_client_for, monkeypatch
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)
    monkeypatch.setattr(
        "freedom_ls.educator_interface.views.send_message",
        lambda **kwargs: SendResult(refusal=MessagingRefusal.NO_RELATIONSHIP),
    )

    response = msg_client_for(educator).post(
        _new_message_url(organisation),
        {
            "recipient": learner.user.pk,
            "body": "Welcome aboard",
            "client_key": str(uuid4()),
        },
    )

    assert response.status_code == 422
    page = lxml.html.fromstring(response.content.decode())
    assert page.xpath("//*[@role='alert'][not(@x-show)]")
    assert "Welcome aboard" in page.xpath("//textarea[@name='body']")[0].text_content()
    assert not inbox_for(educator).exists()


@pytest.mark.django_db
@messages_section
def test_posting_a_blank_new_message_returns_the_modal_at_422(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)

    response = msg_client_for(educator).post(
        _new_message_url(organisation),
        {"recipient": learner.user.pk, "body": "  ", "client_key": str(uuid4())},
    )

    assert response.status_code == 422
    assert "app-modal-title" in response.content.decode()


@pytest.mark.django_db
@messages_section
def test_posting_to_a_learner_of_another_organisation_replaces_only_the_alert(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    foreign = _msg_learner(
        OrganisationFactory(), first_name="Zelda", last_name="Foreign"
    )

    response = msg_client_for(educator).post(
        _new_message_url(organisation),
        {"recipient": foreign.user.pk, "body": "Hi", "client_key": str(uuid4())},
    )

    content = response.content.decode()
    page = lxml.html.fromstring(f"<div>{content}</div>")
    assert response.status_code == 422
    assert response["HX-Retarget"] == "#composer-error"
    assert response["HX-Reswap"] == "outerHTML"
    assert page.xpath("//*[@id='composer-error']//*[@role='alert'][not(@x-show)]")
    assert not page.xpath("//textarea")
    assert "Zelda" not in content
    assert not inbox_for(educator).exists()


@pytest.mark.django_db
@messages_section
def test_posting_to_a_learner_who_left_reads_the_same_as_a_user_who_does_not_exist(
    msg_client_for,
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation, first_name="Bea", last_name="Learner")
    learner.is_active = False
    learner.save()
    client = msg_client_for(educator)

    def post(pk: int):
        return client.post(
            _new_message_url(organisation),
            {"recipient": pk, "body": "Hi", "client_key": str(uuid4())},
        )

    left, absent = post(learner.user.pk), post(999999)

    assert left.status_code == absent.status_code == 422
    assert left.content == absent.content
    assert "Bea" not in left.content.decode()
    assert not inbox_for(educator).exists()


@pytest.mark.django_db
@messages_section
def test_the_new_message_action_is_absent_when_messaging_is_off(
    msg_client_for, settings
):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    settings.MESSAGING_ENABLED = False

    response = msg_client_for(educator).get(_new_message_url(organisation))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_move_shows_on_the_learner_history_tab_as_from_a_to_b(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    source = CohortFactory(organisation=organisation, name="Alpha")
    destination = CohortFactory(organisation=organisation, name="Beta")
    CohortMembershipFactory(learner=learner, cohort=source)
    move_between_cohorts(learner, source, destination, actor=UserFactory())

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [(row[2], row[3]) for row in rows] == [
        ("Moved between cohorts", "From Alpha to Beta")
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

    assert [[(row[2], row[-1]) for row in rows] for rows in shown] == [
        [("Moved between cohorts", "From Alpha to Beta")]
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

    assert ([row[4] for row in rows], "Alpha" in _region_text(other_page)) == (
        ["Alpha"],
        False,
    )


@pytest.mark.django_db
def test_the_cohort_history_tab_renders_its_empty_state(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())

    response = staff_client.get(
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )

    template_names = [t.name for t in response.templates]
    assert "educator_interface/partials/audit_history_empty.html" in template_names


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
    assert [(row[2], row[4]) for row in rows] == [
        ("Cohort registered for course", "Algebra")
    ]


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
    assert (headers, sorted(row[3] for row in rows)) == (
        ["When", "Who", "What", "Target", "Details"],
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
def test_a_learner_registration_shows_on_the_learner_history_tab(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    register_for_course(learner, CourseFactory(title="Algebra"))

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [(row[2], row[3]) for row in rows] == [("Registered for course", "Algebra")]


def _audit_log_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "audit-log")


def _audit_log_rows(document: lxml.html.HtmlElement) -> list[list[str]]:
    return [
        [cell.text_content().strip() for cell in row.cssselect("td")]
        for row in document.cssselect("tbody tr")
    ]


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
    assert headers == ["When", "Who", "What", "Target", "Details"]
    assert row[1:4] == ["Ada Admin", "Cohort created", "Spring cohort"]


@pytest.mark.django_db
def test_the_audit_log_renders_its_empty_state(staff_client: Client):
    organisation = OrganisationFactory()

    response = staff_client.get(_audit_log_url(organisation))

    template_names = [t.name for t in response.templates]
    assert "educator_interface/partials/audit_log_empty.html" in template_names


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
    assert "educator_interface/partials/audit_log_empty.html" in template_names
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
    (details,) = document.cssselect("tbody tr details")
    html = response.content.decode()
    assert (
        row[2],
        row[4].startswith("60 changed, 0 skipped, 0 failed"),
        details.cssselect("summary")[0].text_content().strip(),
        len(details.cssselect("li")),
        "and 10 more" in details.text_content(),
        "<b>bold</b>" in html,
        "&lt;b&gt;bold&lt;/b&gt;" in html,
    ) == ("Bulk action completed", True, "Show 60 entries", 50, True, False, True)


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

    (details,) = document.cssselect("tbody tr details")
    assert (
        details.cssselect("summary")[0].text_content().strip(),
        len(details.cssselect("li")),
    ) == ("Show 1 entries", 1)


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


# bulk run result page


def _run_for(user: User, organisation: Organisation, **fields: object):
    return BulkActionRun.objects.create(
        organisation=organisation,
        requested_by=user,
        table_key="learners",
        action_name="deactivate",
        keys=[str(LearnerFactory(organisation=organisation).pk) for _ in range(2)],
        **fields,
    )


def _run_url(organisation: Organisation, run: BulkActionRun, name: str) -> str:
    return reverse(
        f"educator_interface:{name}",
        kwargs={"organisation_slug": organisation.slug, "run_id": run.pk},
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


@pytest.mark.django_db
def test_a_queued_run_page_polls_its_status_fragment(run_world: SimpleNamespace):
    page = _get_document(
        run_world.client,
        _run_url(run_world.organisation, run_world.run, "bulk_action_run"),
    )

    (status,) = page.cssselect("#run-status")
    assert status.get("role") == "status"
    assert status.get("hx-get") == _run_url(
        run_world.organisation, run_world.run, "bulk_action_run_status"
    )
    assert status.get("hx-trigger") == "every 2s"
    assert page.cssselect("#run-status progress")


@pytest.mark.django_db
def test_a_finished_run_fragment_stops_polling_and_shows_the_summary(
    run_world: SimpleNamespace, mock_site_context: Site
):
    run_bulk_action(str(run_world.run.pk), mock_site_context.pk)

    response = run_world.client.get(
        _run_url(run_world.organisation, run_world.run, "bulk_action_run_status"),
        HTTP_HX_REQUEST="true",
    )

    (status,) = lxml.html.fromstring(response.content.decode()).cssselect("#run-status")
    assert status.get("hx-trigger") is None
    assert "2 learners changed." in status.text_content()
    (back,) = status.cssselect("a")
    assert back.get("href") == _interface_url(run_world.organisation.slug, "learners")


@pytest.mark.django_db
def test_a_failed_run_fragment_says_where_it_stopped(run_world: SimpleNamespace):
    run_world.run.status = RunStatus.FAILED
    run_world.run.processed_count = 1
    run_world.run.error_message = "Unexpected error."
    run_world.run.save()

    response = run_world.client.get(
        _run_url(run_world.organisation, run_world.run, "bulk_action_run_status"),
        HTTP_HX_REQUEST="true",
    )

    text = " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )
    assert "Stopped after 1 of 2 learners." in text
    assert "Unexpected error." in text


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["bulk_action_run", "bulk_action_run_status"])
def test_a_run_is_a_404_for_another_user_of_the_organisation(
    run_world: SimpleNamespace, logged_in_client, name: str
):
    other = cast(User, UserFactory(superuser=True))

    response = logged_in_client(other).get(
        _run_url(run_world.organisation, run_world.run, name)
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["bulk_action_run", "bulk_action_run_status"])
def test_a_run_is_a_404_through_another_organisations_slug(
    run_world: SimpleNamespace, name: str
):
    elsewhere = OrganisationFactory()

    response = run_world.client.get(_run_url(elsewhere, run_world.run, name))

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_run_page_renders_inside_the_interface_shell(run_world: SimpleNamespace):
    page = _get_document(
        run_world.client,
        _run_url(run_world.organisation, run_world.run, "bulk_action_run"),
    )

    assert page.cssselect("#organisation-switcher")
    assert page.cssselect("#main-content h1")
    assert page.cssselect("nav a[aria-current='page']")


@pytest.mark.django_db
def test_the_learners_bar_offers_the_cohort_actions_as_buttons_and_the_rest_under_more(
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

    assert labels("div[data-total-count] > div > div > button[formaction]") == [
        "Add to cohort",
        "Remove from cohort",
    ]
    assert labels("[role='menu'] button[formaction]") == [
        "Deactivate",
        "Reactivate",
        "Register for course",
        "Unregister from course",
        "Resend setup email",
    ]


@pytest.mark.django_db
def test_the_cohorts_bar_offers_the_registration_actions_as_buttons_and_the_state_actions_under_more(
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

    assert labels("div[data-total-count] > div > div > button[formaction]") == [
        "Register for course",
        "Unregister from course",
    ]
    assert labels("[role='menu'] button[formaction]") == ["Deactivate", "Reactivate"]


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
    assert page.cssselect("code")[0].text == "email,first_name,last_name,cohort"
    assert page.cssselect("ol li[aria-current='step']")
    assert "Step 1 of 3" in page.text_content()


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
    assert "New account: 2" in text
    assert "Already a member: 1" in text
    assert "Error: 1" in text
    assert "1 row with errors will not be added." in text
    assert "2 new accounts will get a setup email." in text
    assert [
        button.text_content().strip()
        for button in page.cssselect("#main-content button[type=submit]")
    ] == ["Add 2 learners"]
    assert len(page.cssselect("tbody tr")) == 4


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

    emails = [cell.text for cell in page.cssselect("table tbody tr td:nth-child(2)")]
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

    next_link = first.cssselect("a[rel='next']")[0]
    assert (
        len(first.cssselect("table tbody tr")),
        len(second.cssselect("table tbody tr")),
        next_link.get("href"),
    ) == (50, 1, "?label=error&page=2")


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
        ["Download the 1 error row"],
        [],
    )


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
