"""The educator interface's Learners section.

LearnerConfig lists Learner rows scoped by learners_visible_to. This module
checks the section renders under its name and scoping, and that the
Registered Courses column resolves through its renamed cell template.
"""

from __future__ import annotations

import uuid
from typing import cast

import lxml.html
import pytest

from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.views import LearnerDataTable
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _make_cohort(*, organisation: Organisation) -> Cohort:
    return cast(
        Cohort, CohortFactory(organisation=organisation, name=f"Cohort {uuid.uuid4()}")
    )


def _make_learner(*, organisation: Organisation, **user_fields: str) -> Learner:
    """A learner in ``organisation``, named by default so the tests can assert
    on what the rendered row says."""
    return cast(
        Learner,
        LearnerFactory(
            user=UserFactory(
                **{"first_name": "Ada", "last_name": "Lovelace", **user_fields}
            ),
            organisation=organisation,
        ),
    )


@pytest.fixture
def educator_client(logged_in_client):
    """Factory: a logged-in staff educator holding ``role`` on ``target`` --
    the organisation for a role holder, a cohort for a grant-only educator."""

    def _make(
        target: Organisation | Cohort, role: str = "organisation_admin"
    ) -> Client:
        educator = UserFactory(staff=True)
        assign_object_role(educator, target, role)
        return cast(Client, logged_in_client(educator))

    return _make


def _learners_url(organisation_slug: str, path_string: str = "learners") -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


@pytest.mark.django_db
def test_learners_section_lists_a_learner_visible_to_an_organisation_role_holder(
    educator_client,
):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Learners" in content
    assert "Ada" in content


def _make_pending_learner(*, organisation: Organisation, **user_fields: str) -> Learner:
    learner = _make_learner(organisation=organisation, **user_fields)
    learner.user.set_unusable_password()
    learner.user.save(update_fields=["password"])
    return learner


@pytest.mark.django_db
def test_learners_list_shows_a_pending_learners_badge(educator_client):
    organisation = OrganisationFactory()
    _make_pending_learner(organisation=organisation)

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    (row_status,) = document.xpath(
        "//*[@id='learners-table']//*[normalize-space()='Pending']"
        "[not(.//*[normalize-space()='Pending'])]"
    )[:1]
    assert row_status is not None


@pytest.mark.django_db
def test_learners_list_hides_a_removed_learner_by_default(educator_client):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)
    removed = _make_learner(
        organisation=organisation, first_name="Grace", last_name="Hopper"
    )
    removed.is_active = False
    removed.save(update_fields=["is_active"])

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    content = response.content.decode()
    assert "Ada" in content
    assert "Grace" not in content


@pytest.mark.django_db
def test_learners_list_shows_a_removed_learner_when_filtered_to_removed(
    educator_client,
):
    organisation = OrganisationFactory()
    removed = _make_learner(
        organisation=organisation, first_name="Grace", last_name="Hopper"
    )
    removed.is_active = False
    removed.save(update_fields=["is_active"])

    response = educator_client(organisation).get(
        _learners_url(organisation.slug), {"learners-status": "removed"}
    )

    assert "Grace" in response.content.decode()


@pytest.mark.django_db
def test_a_removed_learners_detail_page_answers_200(educator_client):
    organisation = OrganisationFactory()
    removed = _make_learner(organisation=organisation)
    removed.is_active = False
    removed.save(update_fields=["is_active"])

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{removed.pk}")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_learners_list_excludes_a_learner_from_another_organisation(educator_client):
    """Paired with a learner who should appear: absence alone would also hold
    on a 404, a login redirect or an error page."""
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)
    _make_learner(
        organisation=OrganisationFactory(), first_name="Grace", last_name="Hopper"
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ada" in content
    assert "Grace" not in content


@pytest.mark.django_db
def test_learner_detail_page_renders_the_underlying_users_name_and_email(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation, email="ada@example.com")

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ada" in content
    assert "ada@example.com" in content


@pytest.mark.django_db
def test_learner_detail_pages_panels_refresh_on_learner_changed(educator_client):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    content = response.content.decode()
    assert content.count('hx-trigger="learnerChanged from:body"') >= 2


@pytest.mark.django_db
def test_learners_list_renders_a_registered_course_through_the_renamed_cell_template(
    educator_client,
):
    organisation = OrganisationFactory()
    LearnerCourseRegistrationFactory(
        learner=_make_learner(organisation=organisation),
        course=CourseFactory(title="Intro to Freedom"),
        is_active=True,
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    assert "Intro to Freedom" in response.content.decode()


@pytest.mark.django_db
def test_cohort_only_educator_cannot_open_a_learner_outside_their_cohort(
    educator_client,
):
    """LearnerConfig.authorise_instance is backed by learners_visible_to, so a
    cohort-scoped educator who can reach the organisation at all still gets a
    404 for a learner outside the cohort they hold a grant on."""
    organisation = OrganisationFactory()
    granted_cohort = _make_cohort(organisation=organisation)
    outside_learner = _make_learner(organisation=organisation)

    response = educator_client(granted_cohort, "cohort_admin").get(
        _learners_url(organisation.slug, f"learners/{outside_learner.pk}")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_cohort_only_educator_can_open_a_member_of_their_own_cohort(
    educator_client,
):
    organisation = OrganisationFactory()
    granted_cohort = _make_cohort(organisation=organisation)
    member = _make_learner(organisation=organisation)
    CohortMembershipFactory(learner=member, cohort=granted_cohort)

    response = educator_client(granted_cohort, "cohort_admin").get(
        _learners_url(organisation.slug, f"learners/{member.pk}")
    )

    assert response.status_code == 200
    assert "Ada" in response.content.decode()


@pytest.mark.django_db
class TestLearnerDataTableQueryCost:
    """The prefetches in LearnerDataTable.get_queryset are what keep the
    Cohorts, Courses and Last active cells' cost from growing with row count."""

    @staticmethod
    def _seed_learners(organisation: Organisation, count: int) -> None:
        """One learner per iteration, in two cohorts that each register a
        course, holding two registrations of their own, with a progress record
        for one -- every cell the prefetches feed."""
        for _ in range(count):
            learner = LearnerFactory(user=UserFactory(), organisation=organisation)
            for _ in range(2):
                cohort = _make_cohort(organisation=organisation)
                CohortMembershipFactory(learner=learner, cohort=cohort)
                CohortCourseRegistrationFactory(
                    cohort=cohort, course=CourseFactory(), is_active=True
                )
            registration = LearnerCourseRegistrationFactory(
                learner=learner, course=CourseFactory(), is_active=True
            )
            LearnerCourseRegistrationFactory(
                learner=learner, course=CourseFactory(), is_active=True
            )
            CourseProgressFactory(
                learner=learner,
                course=registration.course,
                learner_registration=registration,
                progress_percentage=40,
            )

    def _render_query_count(
        self, site_aware_request: RequestFactory, learner_count: int
    ) -> int:
        organisation = OrganisationFactory()
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_admin")
        self._seed_learners(organisation, learner_count)

        request = site_aware_request.get("/")
        request.user = educator
        request.organisation = organisation
        request.panel_url_kwargs = {"organisation_slug": organisation.slug}

        query = LearnerDataTable.parse_query(request, "learners")
        queryset = LearnerDataTable.filter_queryset(
            request, LearnerDataTable.get_queryset(request), query
        )
        with CaptureQueriesContext(connection) as captured:
            render_to_string(
                "panel_framework/panels/data_table_region.html",
                LearnerDataTable.get_context(
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

    def test_query_count_does_not_grow_with_learner_count(self, site_aware_request):
        """Compares the two row counts rather than bounding both by a ceiling:
        a ceiling with any slack in it lets one extra query per row hide under
        the bound, which is the only thing this test exists to catch."""
        one_learner = self._render_query_count(site_aware_request, learner_count=1)
        four_learners = self._render_query_count(site_aware_request, learner_count=4)

        assert one_learner == four_learners


@pytest.mark.django_db
def test_learner_detail_cohorts_card_rows_end_with_a_decorative_open_page_icon(
    educator_client,
):
    """The cohort name opens the cohort's page, so its card line ends with
    the open-page icon the framework draws for a link column."""
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    CohortMembershipFactory(
        learner=learner, cohort=_make_cohort(organisation=organisation)
    )

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    document = lxml.html.fromstring(response.content.decode())
    (row,) = document.cssselect("#cohorts-table ul li")
    (primary_line,) = row.cssselect("[data-card-primary-line]")
    (decoration,) = primary_line.xpath("./*[last()][@aria-hidden='true']")
    assert decoration.cssselect("svg")


@pytest.mark.django_db
def test_learners_mobile_toolbar_offers_sort_and_filter(educator_client):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    assert document.xpath("//button[normalize-space()='Sort']")
    assert document.xpath("//button[normalize-space()='Filter']")


@pytest.mark.django_db
def test_learner_detail_page_renders_details_and_cohorts_cards_with_definition_labels(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    document = lxml.html.fromstring(response.content.decode())
    headings = [h.text_content().strip() for h in document.cssselect("h2")]
    labels = [dt.text_content().strip() for dt in document.cssselect("dl dt")]
    assert "Details" in headings
    assert "Cohorts" in headings
    assert labels == ["First name", "Last name", "Email"]


@pytest.mark.django_db
def test_learner_detail_cohorts_panel_lists_an_inactive_cohort_with_its_badge(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    cohort = CohortFactory(
        organisation=organisation, name="Retired group", is_active=False
    )
    CohortMembershipFactory(learner=learner, cohort=cohort)

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    document = lxml.html.fromstring(response.content.decode())
    (row,) = document.xpath(
        "//*[@id='cohorts-table']//li[contains(., 'Retired group')]"
    )
    assert "Inactive" in row.text_content()


@pytest.mark.django_db
def test_learner_detail_cohorts_panel_renders_no_filter_toolbar(educator_client):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    CohortMembershipFactory(
        learner=learner, cohort=_make_cohort(organisation=organisation)
    )

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    document = lxml.html.fromstring(response.content.decode())
    assert not document.xpath(
        "//*[@id='cohorts-table']//*[contains(., 'Show inactive')]"
    )
    assert not document.xpath(
        "//*[@id='cohorts-table']//button[normalize-space()='Filter']"
    )


@pytest.mark.django_db
def test_learners_list_links_a_learner_with_no_name_by_their_email(educator_client):
    organisation = OrganisationFactory()
    learner = _make_learner(
        organisation=organisation,
        first_name="",
        last_name="",
        email="nameless@example.com",
    )
    learner_path = _learners_url(organisation.slug, f"learners/{learner.pk}")

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())
    links = document.xpath(f'//a[@href="{learner_path}"][not(@aria-controls)]')
    # The desktop row and the mobile card both link the learner.
    assert {"nameless@example.com" in link.text_content() for link in links} == {True}
    assert document.xpath(
        f'//*[@hx-get="{learner_path}/__quick-view"]'
        '[@aria-label="Quick view: nameless@example.com"]'
    )


def _learner_cells(response, learner_path: str):
    document = lxml.html.fromstring(response.content.decode())
    return document, document.xpath(f'//a[@href="{learner_path}"][not(@aria-controls)]')


@pytest.mark.django_db
def test_learners_list_cell_links_the_row_and_carries_a_quick_view_trigger(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation, email="ada@example.com")
    learner_path = _learners_url(organisation.slug, f"learners/{learner.pk}")

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    document, links = _learner_cells(response, learner_path)
    assert links
    assert "Ada Lovelace" in links[0].text_content()
    assert "ada@example.com" in links[0].text_content()
    assert document.xpath(
        f'//*[@hx-get="{learner_path}/__quick-view"]'
        '[@aria-label="Quick view: Ada Lovelace"]'
    )


@pytest.mark.django_db
def test_cohort_learners_tab_cell_links_the_row_and_carries_a_quick_view_trigger(
    educator_client,
):
    organisation = OrganisationFactory()
    cohort = _make_cohort(organisation=organisation)
    learner = _make_learner(organisation=organisation)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    learner_path = _learners_url(organisation.slug, f"learners/{learner.pk}")

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners")
    )

    document, links = _learner_cells(response, learner_path)
    assert links
    assert document.xpath(
        f'//*[@hx-get="{learner_path}/__quick-view"]'
        '[@aria-label="Quick view: Ada Lovelace"]'
    )


@pytest.mark.django_db
def test_course_direct_registrations_cell_links_the_row_and_carries_a_quick_view_trigger(
    educator_client,
):
    organisation = OrganisationFactory()
    course = CourseFactory()
    learner = _make_learner(organisation=organisation)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    learner_path = _learners_url(organisation.slug, f"learners/{learner.pk}")

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"courses/{course.pk}/__panels/learners")
    )

    document, links = _learner_cells(response, learner_path)
    assert links
    assert document.xpath(
        f'//*[@hx-get="{learner_path}/__quick-view"]'
        '[@aria-label="Quick view: Ada Lovelace"]'
    )


@pytest.mark.django_db
def test_nameless_learner_cell_has_no_secondary_line_and_the_email_is_the_card_primary_line(
    educator_client,
):
    organisation = OrganisationFactory()
    _make_learner(
        organisation=organisation,
        first_name="",
        last_name="",
        email="nameless@example.com",
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    (primary_line,) = document.cssselect("[data-card-primary-line]")
    assert "nameless@example.com" in primary_line.text_content()
    assert primary_line.text_content().count("nameless@example.com") == 1


@pytest.mark.django_db
def test_learners_list_sorted_by_learner_orders_by_first_name(educator_client):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation, first_name="Zed", email="z@example.com")
    _make_learner(organisation=organisation, first_name="Abe", email="a@example.com")

    response = educator_client(organisation).get(
        _learners_url(organisation.slug), {"sort": "user__first_name"}
    )

    content = response.content.decode()
    assert content.index("Abe") < content.index("Zed")


def _row_cells(response, header: str):
    """The desktop table's cells under the column headed ``header``."""
    document = lxml.html.fromstring(response.content.decode())
    headers = [" ".join(th.text_content().split()) for th in document.cssselect("th")]
    position = headers.index(header) + 1
    return document.cssselect(f"tbody tr td:nth-child({position})")


@pytest.mark.django_db
def test_learners_list_courses_cell_shows_each_active_course_with_its_percentage(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Intro to Freedom"), is_active=True
    )
    CourseProgressFactory(
        learner=learner,
        course=registration.course,
        learner_registration=registration,
        progress_percentage=40,
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "Intro to Freedom" in cell.text_content()
    assert "40%" in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_skips_an_inactive_individual_registration(
    educator_client,
):
    organisation = OrganisationFactory()
    LearnerCourseRegistrationFactory(
        learner=_make_learner(organisation=organisation),
        course=CourseFactory(title="Dropped Course"),
        is_active=False,
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "Dropped Course" not in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_lists_a_course_from_an_active_cohort(
    educator_client,
):
    organisation = OrganisationFactory()
    cohort = _make_cohort(organisation=organisation)
    CohortMembershipFactory(
        learner=_make_learner(organisation=organisation), cohort=cohort
    )
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Cohort Course"), is_active=True
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "Cohort Course" in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_skips_a_course_from_an_inactive_cohort(
    educator_client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(
        organisation=organisation, name=f"Cohort {uuid.uuid4()}", is_active=False
    )
    CohortMembershipFactory(
        learner=_make_learner(organisation=organisation), cohort=cohort
    )
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Hidden Course"), is_active=True
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "Hidden Course" not in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_shows_the_higher_of_two_records_for_one_course(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    course = CourseFactory(title="Shared Course")
    individual = LearnerCourseRegistrationFactory(
        learner=learner, course=course, is_active=True
    )
    cohort = _make_cohort(organisation=organisation)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    cohort_registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=course, is_active=True
    )
    CourseProgressFactory(
        learner=learner,
        course=course,
        learner_registration=individual,
        progress_percentage=20,
    )
    CourseProgressFactory(
        learner=learner,
        course=course,
        learner_registration=None,
        cohort_registration=cohort_registration,
        progress_percentage=70,
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "70%" in cell.text_content()
    assert "20%" not in cell.text_content()


@pytest.mark.django_db
def test_learners_list_last_active_reads_never_without_a_progress_record(
    educator_client,
):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Last active")
    assert cell.text_content().strip() == "Never"


@pytest.mark.django_db
def test_learners_list_sorted_by_last_active_orders_by_most_recent_visit(
    educator_client,
):
    organisation = OrganisationFactory()
    for first_name, visited in (("Early", "2024-01-01"), ("Late", "2025-06-01")):
        learner = _make_learner(
            organisation=organisation,
            first_name=first_name,
            email=f"{first_name.lower()}@visit.example.com",
        )
        CourseProgressFactory(
            learner=learner, last_accessed_time=f"{visited}T10:00:00+00:00"
        )

    response = educator_client(organisation).get(
        _learners_url(organisation.slug), {"learners-sort": "-last_active"}
    )

    content = response.content.decode()
    assert content.index("late@visit") < content.index("early@visit")


@pytest.mark.django_db
def test_learners_table_row_label_is_the_display_name():
    learner = LearnerFactory(user=UserFactory(first_name="Ada", last_name="Lovelace"))

    assert LearnerDataTable.get_row_label(learner) == learner.user.display_name
