"""The educator interface's section configs and the pages they render."""

from __future__ import annotations

from collections.abc import Callable

import lxml.html
import pytest

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.views import CohortDataTable
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort
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


# A cohort page holds two tables, its course registrations on the Details
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
    details_tab = client.get(_cohort_url(cohort), {"learners-page": "2"})

    assert learners_tab.status_code == 200
    content = learners_tab.content.decode()
    # The learners table is on its own page 2: the last learner shows, the
    # 1st (on page 1) does not.
    assert f"Learner{DataTable.page_size:02d}" in content
    assert "Learner00" not in content
    # The course registrations table is untouched, still on page 1.
    assert details_tab.status_code == 200
    content = details_tab.content.decode()
    assert "Course 0" in content
    assert "Course 1" in content


@pytest.mark.django_db
def test_renaming_a_cohort_onto_a_sibling_name_answers_422_and_keeps_the_name(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = staff_client.post(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__actions/edit"),
        {"name": "Year 10 Science"},
        HTTP_HX_REQUEST="true",
    )

    cohort.refresh_from_db()
    assert response.status_code == 422
    assert "Another cohort already has this name." in response.content.decode()
    assert cohort.name == "Year 11 Science"


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
