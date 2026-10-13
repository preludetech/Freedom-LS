"""The educator interface's section configs and the pages they render."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast
from uuid import uuid4

import lxml.html
import pytest

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging import (
    SendResult,
    inbox_for,
    unread_conversation_count,
)
from freedom_ls.comms.messaging_policy import MessagingDecision, MessagingRefusal
from freedom_ls.comms.models import Conversation
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.events import COHORT_CHANGED
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
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.tables import DataTable


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
def test_cohort_detail_page_has_overview_learners_courses_and_settings_tabs(
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
        "settings",
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
def test_needs_attention_card_renders_its_placeholder(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    (card,) = document.cssselect("section[data-panel='attention']")
    assert "Nothing needs attention yet." in card.text_content()


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
        f"cohorts/{cohort.pk}/__tabs/courses/__actions/unregister",
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
def test_posting_to_a_learner_of_another_organisation_is_a_404(msg_client_for):
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    foreign = _msg_learner(OrganisationFactory())

    response = msg_client_for(educator).post(
        _new_message_url(organisation),
        {"recipient": foreign.user.pk, "body": "Hi", "client_key": str(uuid4())},
    )

    assert response.status_code == 404
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
