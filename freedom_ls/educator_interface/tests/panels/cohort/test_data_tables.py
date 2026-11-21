"""Tests for the cohort tables."""

from __future__ import annotations

from datetime import UTC, datetime

import lxml.html
import pytest

from django.db import connection
from django.http import QueryDict
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext

from freedom_ls.content_engine.factories import (
    CourseFactory,
)
from freedom_ls.educator_interface.panels.cohort.data_tables import (
    CohortDataTable,
)
from freedom_ls.educator_interface.panels.common.filters import VisibleCourseFilter
from freedom_ls.educator_interface.tests.helpers import (
    _educator_request,
    _get_document,
    _interface_url,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.filters import TableFilter, ToggleFilter
from freedom_ls.panel_framework.tables import TableQuery

# the table hides inactive cohorts only while it offers the toggle


def _cohort_rows(table: type[CohortDataTable], request) -> list[Cohort]:
    query = TableQuery(key="cohorts")
    return list(table.filter_queryset(request, table.get_queryset(request), query))


@pytest.mark.usefixtures("_site_context")
@pytest.mark.django_db
def test_the_cohort_table_hides_inactive_cohorts_while_its_toggle_is_unset(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation)
    CohortFactory(organisation=organisation, is_active=False)

    assert _cohort_rows(CohortDataTable, request) == [active]


@pytest.mark.usefixtures("_site_context")
@pytest.mark.django_db
def test_a_cohort_table_without_the_toggle_keeps_inactive_cohorts(
    site_aware_request: RequestFactory,
):
    """Only the toggle narrows the table: another filter list, with
    nothing on the page to widen it again, must not hide rows."""
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation, name="A")
    inactive = CohortFactory(organisation=organisation, name="B", is_active=False)

    class CourseOnlyCohortDataTable(CohortDataTable):
        @classmethod
        def get_filters(cls) -> list[TableFilter]:
            return [
                VisibleCourseFilter(
                    "course", "Course", lookup="course_registrations__course"
                )
            ]

    assert _cohort_rows(CourseOnlyCohortDataTable, request) == [active, inactive]


@pytest.mark.usefixtures("_site_context")
@pytest.mark.django_db
def test_the_toggle_is_read_under_whatever_key_the_table_declares_it(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation, name="A")
    inactive = CohortFactory(organisation=organisation, name="B", is_active=False)

    class RenamedToggleCohortDataTable(CohortDataTable):
        inactive_toggle_key = "all"

        @classmethod
        def get_filters(cls) -> list[TableFilter]:
            return [ToggleFilter("all", "Show all")]

    unset = TableQuery(key="cohorts")
    on = TableQuery(key="cohorts", filters={"all": ["1"]})
    queryset = RenamedToggleCohortDataTable.get_queryset(request)

    assert list(
        RenamedToggleCohortDataTable.filter_queryset(request, queryset, unset)
    ) == [active]
    assert list(
        RenamedToggleCohortDataTable.filter_queryset(request, queryset, on)
    ) == [
        active,
        inactive,
    ]


@pytest.mark.usefixtures("_site_context")
@pytest.mark.django_db
def test_another_toggle_listed_first_does_not_stand_in_for_show_inactive(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation, name="A")
    CohortFactory(organisation=organisation, name="B", is_active=False)

    class TwoToggleCohortDataTable(CohortDataTable):
        @classmethod
        def get_filters(cls) -> list[TableFilter]:
            return [ToggleFilter("mine", "Only mine"), *super().get_filters()]

    query = TableQuery(key="cohorts", filters={"mine": ["1"]})
    queryset = TwoToggleCohortDataTable.get_queryset(request)

    assert list(TwoToggleCohortDataTable.filter_queryset(request, queryset, query)) == [
        active
    ]


@pytest.mark.usefixtures("_site_context")
@pytest.mark.django_db
def test_the_cohort_table_widens_to_inactive_cohorts_on_the_inactive_parameter(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation, name="A")
    inactive = CohortFactory(organisation=organisation, name="B", is_active=False)
    request.GET = QueryDict("cohorts-inactive=1")

    query = CohortDataTable.parse_query(request, "cohorts")
    rows = CohortDataTable.filter_queryset(
        request, CohortDataTable.get_queryset(request), query
    )

    assert list(rows) == [active, inactive]


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
