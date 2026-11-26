"""The educator interface's Learners section.

LearnerConfig lists Learner rows scoped by learners_visible_to. This module
checks the section renders under its name and scoping, and that the
Registered Courses column resolves through its renamed cell template.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.educator_interface.panels.learner.data_tables import (
    LearnerDataTable,
    _last_active_cell,
    learner_course_cell,
    learner_course_summaries,
)
from freedom_ls.educator_interface.tests.helpers import (
    RoleHolderClient,
    _get_document,
    _interface_url,
    _notes_for,
    _shared_and_own_course_world,
    _shared_by_notes_by_row,
    organisation_admin_viewer,
    page_after_adding_rows,
    profile_picture_sources,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.reports.tests.helpers import topic_progress
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _make_cohort(*, organisation: Organisation) -> Cohort:
    return cast(
        Cohort, CohortFactory(organisation=organisation, name=f"Cohort {uuid.uuid4()}")
    )


def _make_learner(*, organisation: Organisation, **user_fields: object) -> Learner:
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


def _learners_url(organisation_slug: str, path_string: str = "learners") -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


@pytest.mark.django_db
def test_learners_section_lists_a_learner_visible_to_an_organisation_role_holder(
    role_holder_client,
):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

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
def test_learners_list_cohort_link_is_bold_like_a_person_link(role_holder_client):
    """Cohort names in the Cohorts column used to be medium weight, not bold."""
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    CohortMembershipFactory(learner=learner, cohort=cohort)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    links = document.xpath(f"//a[contains(@href, 'cohorts/{cohort.pk}')]")
    assert links
    assert all("font-bold" in link.get("class") for link in links)


@pytest.mark.django_db
def test_learners_list_shows_a_pending_learners_badge(role_holder_client):
    organisation = OrganisationFactory()
    _make_pending_learner(organisation=organisation)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    (row_status,) = document.xpath(
        "//*[@id='learners-table']//*[normalize-space()='Pending']"
        "[not(.//*[normalize-space()='Pending'])]"
    )[:1]
    assert row_status is not None


@pytest.mark.django_db
def test_learners_list_hides_an_inactive_learner_by_default(role_holder_client):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)
    inactive_learner = _make_learner(
        organisation=organisation, first_name="Grace", last_name="Hopper"
    )
    inactive_learner.is_active = False
    inactive_learner.save(update_fields=["is_active"])

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    content = response.content.decode()
    assert "Ada" in content
    assert "Grace" not in content


@pytest.mark.django_db
def test_learners_list_shows_an_inactive_learner_when_filtered_to_inactive(
    role_holder_client,
):
    organisation = OrganisationFactory()
    inactive_learner = _make_learner(
        organisation=organisation, first_name="Grace", last_name="Hopper"
    )
    inactive_learner.is_active = False
    inactive_learner.save(update_fields=["is_active"])

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug), {"learners-status": "inactive"}
    )

    assert "Grace" in response.content.decode()


@pytest.mark.django_db
def test_learners_list_hides_an_inactive_learner_when_the_status_filter_is_emptied(
    role_holder_client,
):
    """Clear all, the filter sheet's Reset and unticking every status all
    send the status parameter empty."""
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)
    inactive_learner = _make_learner(
        organisation=organisation, first_name="Grace", last_name="Hopper"
    )
    inactive_learner.is_active = False
    inactive_learner.save(update_fields=["is_active"])

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug), {"learners-status": ""}
    )

    content = response.content.decode()
    assert "Ada" in content
    assert "Grace" not in content


@pytest.mark.django_db
def test_learners_list_offers_to_show_all_when_the_default_filter_hides_every_learner(
    role_holder_client,
):
    """ "Clear filters" would return to Active + Pending and show nothing again,
    so the way out is a link that selects every status."""
    organisation = OrganisationFactory()
    inactive_learner = _make_learner(
        organisation=organisation, first_name="Grace", last_name="Hopper"
    )
    inactive_learner.is_active = False
    inactive_learner.save(update_fields=["is_active"])
    client = role_holder_client(organisation)

    response = client.get(_learners_url(organisation.slug))

    content = response.content.decode()
    assert "No learners match these filters." in content
    assert "No learners yet" not in content
    document = lxml.html.fromstring(content)
    (href,) = {
        link.get("href")
        for link in document.xpath("//a[normalize-space()='Show all learners']")
    }
    assert "Grace" in client.get(href).content.decode()


@pytest.mark.django_db
def test_learners_list_shows_the_first_use_state_when_there_are_no_learners(
    role_holder_client,
):
    organisation = OrganisationFactory()

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    content = response.content.decode()
    assert "No learners yet." in content
    assert "No learners match these filters." not in content


@pytest.mark.django_db
def test_learners_status_chip_has_no_remove_control_at_its_default(role_holder_client):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    assert document.xpath("//*[@id='learners-table']//summary") != []
    assert document.xpath("//a[@aria-label='Remove Status filter']") == []


@pytest.mark.django_db
@pytest.mark.parametrize("link_text", ["Clear all", "Reset"])
def test_clearing_the_status_filter_returns_to_active_and_pending(
    role_holder_client, link_text
):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)
    _make_pending_learner(
        organisation=organisation, first_name="Grace", last_name="Hopper"
    )
    inactive_learner = _make_learner(
        organisation=organisation, first_name="Alan", last_name="Turing"
    )
    inactive_learner.is_active = False
    inactive_learner.save(update_fields=["is_active"])
    client = role_holder_client(organisation)
    filtered = client.get(
        _learners_url(organisation.slug), {"learners-status": "inactive"}
    )
    filtered_document = lxml.html.fromstring(filtered.content.decode())
    (href,) = {
        link.get("href")
        for link in filtered_document.xpath(f"//a[normalize-space()='{link_text}']")
    }

    response = client.get(href)

    content = response.content.decode()
    assert "Ada" in content
    assert "Grace" in content
    assert "Alan" not in content


@pytest.mark.django_db
def test_an_inactive_learners_detail_page_answers_200(role_holder_client):
    organisation = OrganisationFactory()
    inactive_learner = _make_learner(organisation=organisation)
    inactive_learner.is_active = False
    inactive_learner.save(update_fields=["is_active"])

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{inactive_learner.pk}")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_learners_list_excludes_a_learner_from_another_organisation(role_holder_client):
    """Paired with a learner who should appear: absence alone would also hold
    on a 404, a login redirect or an error page."""
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)
    _make_learner(
        organisation=OrganisationFactory(), first_name="Grace", last_name="Hopper"
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ada" in content
    assert "Grace" not in content


@pytest.mark.django_db
def test_learner_detail_page_renders_the_underlying_users_name_and_email(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation, email="ada@example.com")

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ada" in content
    assert "ada@example.com" in content


@pytest.mark.django_db
def test_learner_detail_pages_panels_refresh_on_learner_changed(role_holder_client):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    content = response.content.decode()
    assert content.count('hx-trigger="learnerChanged from:body') >= 2


@pytest.mark.django_db
def test_learners_list_renders_a_registered_course_through_the_renamed_cell_template(
    role_holder_client,
):
    organisation = OrganisationFactory()
    LearnerCourseRegistrationFactory(
        learner=_make_learner(organisation=organisation),
        course=CourseFactory(title="Intro to Freedom"),
        is_active=True,
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    assert "Intro to Freedom" in response.content.decode()


@pytest.mark.django_db
def test_cohort_only_educator_cannot_open_a_learner_outside_their_cohort(
    role_holder_client,
):
    """LearnerConfig.authorise_instance is backed by learners_visible_to, so a
    cohort-scoped educator who can reach the organisation at all still gets a
    404 for a learner outside the cohort they hold a grant on."""
    organisation = OrganisationFactory()
    granted_cohort = _make_cohort(organisation=organisation)
    outside_learner = _make_learner(organisation=organisation)

    response = role_holder_client(granted_cohort, "cohort_admin").get(
        _learners_url(organisation.slug, f"learners/{outside_learner.pk}")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_cohort_only_educator_can_open_a_member_of_their_own_cohort(
    role_holder_client,
):
    organisation = OrganisationFactory()
    granted_cohort = _make_cohort(organisation=organisation)
    member = _make_learner(organisation=organisation)
    CohortMembershipFactory(learner=member, cohort=granted_cohort)

    response = role_holder_client(granted_cohort, "cohort_admin").get(
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
        course, holding two registrations of their own, each course placing topics,
        with a progress record for one -- every cell the prefetches feed."""
        for _ in range(count):
            learner = LearnerFactory(user=UserFactory(), organisation=organisation)
            for _ in range(2):
                cohort = _make_cohort(organisation=organisation)
                CohortMembershipFactory(learner=learner, cohort=cohort)
                CohortCourseRegistrationFactory(
                    cohort=cohort,
                    course=_course_with_topics(f"Course {uuid.uuid4()}", 2)[0],
                    is_active=True,
                )
            registration = LearnerCourseRegistrationFactory(
                learner=learner,
                course=_course_with_topics(f"Course {uuid.uuid4()}", 2)[0],
                is_active=True,
            )
            LearnerCourseRegistrationFactory(
                learner=learner,
                course=_course_with_topics(f"Course {uuid.uuid4()}", 2)[0],
                is_active=True,
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
    role_holder_client,
):
    """The cohort name opens the cohort's page, so its card line ends with
    the open-page icon the framework draws for a link column."""
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    CohortMembershipFactory(
        learner=learner, cohort=_make_cohort(organisation=organisation)
    )

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    document = lxml.html.fromstring(response.content.decode())
    (row,) = document.cssselect("#cohorts-table ul li")
    (primary_line,) = row.cssselect("[data-card-primary-line]")
    (decoration,) = primary_line.xpath("./*[last()][@aria-hidden='true']")
    assert decoration.cssselect("svg")


@pytest.mark.django_db
def test_learners_mobile_toolbar_offers_sort_and_filter(role_holder_client):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    assert document.xpath("//button[normalize-space()='Sort']")
    assert document.xpath("//button[normalize-space()='Filter']")


@pytest.mark.django_db
def test_learner_detail_page_renders_details_and_cohorts_cards_with_definition_labels(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    document = lxml.html.fromstring(response.content.decode())
    headings = [h.text_content().strip() for h in document.cssselect("h2")]
    labels = [dt.text_content().strip() for dt in document.cssselect("dl dt")]
    assert "Details" in headings
    assert "Cohorts" in headings
    assert labels[:4] == ["Name", "Email", "Status", "Date added"]


@pytest.mark.django_db
def test_learner_detail_cohorts_panel_lists_an_inactive_cohort_with_its_badge(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    cohort = CohortFactory(
        organisation=organisation, name="Retired group", is_active=False
    )
    CohortMembershipFactory(learner=learner, cohort=cohort)

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    document = lxml.html.fromstring(response.content.decode())
    (row,) = document.xpath(
        "//*[@id='cohorts-table']//li[contains(., 'Retired group')]"
    )
    assert "Inactive" in row.text_content()


@pytest.mark.django_db
def test_learner_detail_cohorts_panel_renders_no_filter_toolbar(role_holder_client):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    CohortMembershipFactory(
        learner=learner, cohort=_make_cohort(organisation=organisation)
    )

    response = role_holder_client(organisation).get(
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
def test_learners_list_links_a_learner_with_no_name_by_their_email(role_holder_client):
    organisation = OrganisationFactory()
    learner = _make_learner(
        organisation=organisation,
        first_name="",
        last_name="",
        email="nameless@example.com",
    )
    learner_path = _learners_url(organisation.slug, f"learners/{learner.pk}")

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

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
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation, email="ada@example.com")
    learner_path = _learners_url(organisation.slug, f"learners/{learner.pk}")

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

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
    role_holder_client,
):
    organisation = OrganisationFactory()
    cohort = _make_cohort(organisation=organisation)
    learner = _make_learner(organisation=organisation)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    learner_path = _learners_url(organisation.slug, f"learners/{learner.pk}")

    response = role_holder_client(organisation).get(
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
    role_holder_client,
):
    organisation = OrganisationFactory()
    course = CourseFactory()
    learner = _make_learner(organisation=organisation)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    learner_path = _learners_url(organisation.slug, f"learners/{learner.pk}")

    response = role_holder_client(organisation).get(
        _learners_url(
            organisation.slug, f"courses/{course.pk}/__tabs/overview/__panels/learners"
        )
    )

    document, links = _learner_cells(response, learner_path)
    assert links
    assert document.xpath(
        f'//*[@hx-get="{learner_path}/__quick-view"]'
        '[@aria-label="Quick view: Ada Lovelace"]'
    )


@pytest.mark.django_db
def test_nameless_learner_cell_has_no_secondary_line_and_the_email_is_the_card_primary_line(
    role_holder_client,
):
    organisation = OrganisationFactory()
    _make_learner(
        organisation=organisation,
        first_name="",
        last_name="",
        email="nameless@example.com",
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    (primary_line,) = document.cssselect("[data-card-primary-line]")
    assert "nameless@example.com" in primary_line.text_content()
    assert primary_line.text_content().count("nameless@example.com") == 1


@pytest.mark.django_db
def test_learners_list_sorted_by_learner_orders_by_first_name(role_holder_client):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation, first_name="Abe", email="a@example.com")
    _make_learner(organisation=organisation, first_name="Zed", email="z@example.com")

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug), {"learners-sort": "-user__first_name"}
    )

    content = response.content.decode()
    assert content.index("Zed") < content.index("Abe")


def _row_cells(response, header: str):
    """The desktop table's cells under the column headed ``header``."""
    document = lxml.html.fromstring(response.content.decode())
    headers = [" ".join(th.text_content().split()) for th in document.cssselect("th")]
    position = headers.index(header) + 1
    return document.cssselect(f"tbody tr td:nth-child({position})")


def _course_with_topics(title: str, topic_count: int) -> tuple[Course, list[Topic]]:
    """A course placing `topic_count` topics, so its completion is recomputed
    from them."""
    course: Course = CourseFactory(title=title)
    topics: list[Topic] = []
    for order in range(topic_count):
        topic: Topic = TopicFactory()
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=order
        )
        topics.append(topic)
    return course, topics


def _complete_topics(
    record: CourseProgress,
    topics: list[Topic],
    count: int,
    *,
    completed_days_ago: int = 0,
) -> None:
    for topic in topics[:count]:
        topic_progress(
            record,
            topic,
            complete_time=timezone.now() - timedelta(days=completed_days_ago),
        )


def _set_last_accessed(record: CourseProgress, days_ago: int) -> None:
    """Write `last_accessed_time` past its auto_now."""
    CourseProgress.objects.filter(pk=record.pk).update(
        last_accessed_time=timezone.now() - timedelta(days=days_ago)
    )


def _course_titles(response) -> list[str]:
    (cell,) = _row_cells(response, "Courses")
    return [
        " ".join(title.text_content().split())
        for title in cell.cssselect("li span.truncate")
    ]


def _registered_with_progress(
    learner: Learner,
    title: str,
    *,
    topic_count: int,
    completed: int,
    completed_days_ago: int = 0,
    accessed_days_ago: int | None = None,
) -> CourseProgress:
    course, topics = _course_with_topics(title, topic_count)
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=course, is_active=True
    )
    record: CourseProgress = CourseProgressFactory(
        learner=learner, course=course, learner_registration=registration
    )
    _complete_topics(record, topics, completed, completed_days_ago=completed_days_ago)
    if accessed_days_ago is not None:
        _set_last_accessed(record, accessed_days_ago)
    return record


@pytest.mark.django_db
def test_learners_list_courses_cell_shows_each_active_course_with_its_percentage(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    _registered_with_progress(learner, "Intro to Freedom", topic_count=5, completed=2)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "Intro to Freedom" in cell.text_content()
    assert "40%" in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_skips_an_inactive_individual_registration(
    role_holder_client,
):
    organisation = OrganisationFactory()
    LearnerCourseRegistrationFactory(
        learner=_make_learner(organisation=organisation),
        course=CourseFactory(title="Dropped Course"),
        is_active=False,
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "Dropped Course" not in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_lists_a_course_from_an_active_cohort(
    role_holder_client,
):
    organisation = OrganisationFactory()
    cohort = _make_cohort(organisation=organisation)
    CohortMembershipFactory(
        learner=_make_learner(organisation=organisation), cohort=cohort
    )
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Cohort Course"), is_active=True
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "Cohort Course" in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_skips_a_course_from_an_inactive_cohort(
    role_holder_client,
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

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "Hidden Course" not in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_shows_the_higher_of_two_records_for_one_course(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    course, topics = _course_with_topics("Shared Course", 10)
    individual = LearnerCourseRegistrationFactory(
        learner=learner, course=course, is_active=True
    )
    cohort = _make_cohort(organisation=organisation)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    cohort_registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=course, is_active=True
    )
    individual_record = CourseProgressFactory(
        learner=learner, course=course, learner_registration=individual
    )
    cohort_record = CourseProgressFactory(
        learner=learner,
        course=course,
        learner_registration=None,
        cohort_registration=cohort_registration,
    )
    _complete_topics(individual_record, topics, 2)
    _complete_topics(cohort_record, topics, 7)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert "70%" in cell.text_content()
    assert "20%" not in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_puts_a_flagged_course_before_a_more_recently_active_one(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    _registered_with_progress(
        learner, "Under way", topic_count=4, completed=1, accessed_days_ago=0
    )
    _registered_with_progress(
        learner,
        "Gone quiet",
        topic_count=4,
        completed=1,
        completed_days_ago=30,
        accessed_days_ago=20,
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    assert _course_titles(response) == ["Gone quiet", "Under way"]


@pytest.mark.django_db
def test_learners_list_courses_cell_puts_in_progress_before_complete_and_not_started(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    _registered_with_progress(learner, "A complete", topic_count=2, completed=2)
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="B not started"), is_active=True
    )
    _registered_with_progress(learner, "C under way", topic_count=4, completed=1)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    assert _course_titles(response)[0] == "C under way"


@pytest.mark.django_db
def test_learners_list_courses_cell_orders_a_group_by_latest_activity_then_title(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    for title, days_ago in (
        ("Older", 5),
        ("Newest", 1),
        ("Tied B", 3),
        ("Tied A", 3),
    ):
        _registered_with_progress(
            learner, title, topic_count=4, completed=1, accessed_days_ago=days_ago
        )
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Aardvark"), is_active=True
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    assert _course_titles(response)[:3] == ["Newest", "Tied A", "Tied B"]


@pytest.mark.django_db
def test_learners_list_courses_cell_puts_a_course_with_no_activity_last_in_its_group(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Aardvark"), is_active=True
    )
    _registered_with_progress(
        learner, "Zebra", topic_count=2, completed=2, accessed_days_ago=2
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    assert _course_titles(response) == ["Zebra", "Aardvark"]


@pytest.mark.django_db
def test_learners_list_courses_cell_flags_a_course_when_only_one_of_its_registrations_is_flagged(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    course, topics = _course_with_topics("Held twice", 4)
    individual = LearnerCourseRegistrationFactory(
        learner=learner, course=course, is_active=True
    )
    cohort = _make_cohort(organisation=organisation)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    cohort_registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=course, is_active=True
    )
    flagged_record = CourseProgressFactory(
        learner=learner, course=course, learner_registration=individual
    )
    fresh_record = CourseProgressFactory(
        learner=learner,
        course=course,
        learner_registration=None,
        cohort_registration=cohort_registration,
    )
    _complete_topics(flagged_record, topics, 1, completed_days_ago=30)
    _complete_topics(fresh_record, topics, 3)
    _registered_with_progress(
        learner, "Aardvark recent", topic_count=4, completed=1, accessed_days_ago=0
    )
    _set_last_accessed(fresh_record, 0)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    assert _course_titles(response)[0] == "Held twice"


@pytest.mark.django_db
def test_learners_export_courses_column_keeps_the_order_found(site_aware_request):
    """The on-screen cell ranks Zebra (in progress) above Aardvark (not
    started) once the page's details are attached; the export lists the courses
    as the registrations were found."""
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation)
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Aardvark"), is_active=True
    )
    _registered_with_progress(learner, "Zebra", topic_count=4, completed=1)
    request = site_aware_request.get("/")
    request.user = organisation_admin_viewer(organisation)
    request.organisation = organisation
    (row,) = LearnerDataTable.get_queryset(request)
    found_order = ", ".join(s.course.title for s in learner_course_summaries(row))
    page = LearnerDataTable.get_rows(
        request,
        [row],
        LearnerDataTable.parse_query(request, "learners"),
    )
    (courses_column,) = [
        c for c in LearnerDataTable.get_export_columns() if c.header == "Courses"
    ]

    assert [s.course.title for s in learner_course_cell(page.object_list[0]).shown] == [
        "Zebra",
        "Aardvark",
    ]
    assert courses_column.cell(page.object_list[0]) == found_order


def _learner_on_courses(organisation: Organisation, count: int) -> Learner:
    learner = _make_learner(organisation=organisation)
    for number in range(count):
        LearnerCourseRegistrationFactory(
            learner=learner,
            course=CourseFactory(title=f"Course {number}"),
            is_active=True,
        )
    return learner


@pytest.mark.django_db
def test_learners_list_courses_cell_caps_at_three_and_links_the_rest_to_the_courses_tab(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _learner_on_courses(organisation, 5)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert len(cell.cssselect("li")) == 3
    (more,) = cell.xpath(".//a[starts-with(@aria-label, '+2 more')]")
    assert more.get("href").endswith(f"learners/{learner.pk}/__tabs/courses")
    assert "Ada Lovelace" in more.get("aria-label")
    assert more.text_content().strip() == "+2 more"


@pytest.mark.django_db
def test_learners_list_courses_cell_with_three_courses_has_no_more_link(
    role_holder_client,
):
    organisation = OrganisationFactory()
    _learner_on_courses(organisation, 3)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    assert len(cell.cssselect("li")) == 3
    assert "more" not in cell.text_content()


@pytest.mark.django_db
def test_learners_list_courses_cell_names_each_bar_after_its_course(
    role_holder_client,
):
    organisation = OrganisationFactory()
    _learner_on_courses(organisation, 1)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    (bar,) = cell.cssselect("progress")
    assert bar.get("aria-label") == "Course 0 progress"


@pytest.mark.django_db
def test_learners_list_courses_cell_without_a_progress_record_reads_an_empty_bar(
    role_holder_client,
):
    organisation = OrganisationFactory()
    _learner_on_courses(organisation, 1)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Courses")
    (bar,) = cell.cssselect("progress")
    assert bar.get("value") == "0"
    assert "0%" in cell.text_content()


@pytest.mark.django_db
def test_learners_list_phone_card_holds_the_capped_courses_cell(role_holder_client):
    organisation = OrganisationFactory()
    _learner_on_courses(organisation, 5)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    more_links = document.xpath("//a[starts-with(@aria-label, '+2 more')]")
    assert len(more_links) == 2  # one in the desktop table, one in the phone card


@pytest.mark.django_db
def test_learners_list_last_active_reads_never_for_a_user_never_active(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation, last_active=None)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Last active")
    assert cell.text_content().strip() == "Never"


@pytest.mark.django_db
def test_learners_list_last_active_shows_the_users_date_not_course_activity(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    learner = _make_learner(
        organisation=organisation,
        last_active=datetime(2020, 1, 2, 9, 0, tzinfo=UTC),
    )
    CourseProgressFactory(learner=learner, last_accessed_time=timezone.now())

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    (cell,) = _row_cells(response, "Last active")
    assert cell.text_content().strip() == "2 Jan 2020"


@pytest.mark.django_db
def test_learners_list_sorted_by_last_active_orders_by_the_most_recent_request(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    for first_name, active in (
        ("Early", datetime(2024, 1, 1, 10, 0, tzinfo=UTC)),
        ("Late", datetime(2025, 6, 1, 10, 0, tzinfo=UTC)),
    ):
        _make_learner(
            organisation=organisation,
            first_name=first_name,
            email=f"{first_name.lower()}@visit.example.com",
            last_active=active,
        )

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug), {"learners-sort": "-user__last_active"}
    )

    content = response.content.decode()
    assert content.index("late@visit") < content.index("early@visit")


@pytest.mark.django_db
def test_learners_export_last_active_cell_is_the_users_local_date() -> None:
    learner = LearnerFactory(
        user=UserFactory(last_active=datetime(2026, 3, 4, 15, 30, tzinfo=UTC))
    )

    assert _last_active_cell(learner) == "2026-03-04"


@pytest.mark.django_db
def test_learners_export_last_active_cell_is_empty_for_a_user_never_active() -> None:
    learner = LearnerFactory(user=UserFactory(last_active=None))

    assert _last_active_cell(learner) == ""


@pytest.mark.django_db
def test_learners_table_row_label_is_the_display_name():
    learner = LearnerFactory(user=UserFactory(first_name="Ada", last_name="Lovelace"))

    assert LearnerDataTable.get_row_label(learner) == learner.user.display_name


@pytest.mark.django_db
def test_learners_list_row_checkbox_is_labelled_by_the_email_of_a_nameless_learner(
    role_holder_client,
):
    organisation = OrganisationFactory()
    _make_learner(
        organisation=organisation,
        first_name="",
        last_name="",
        email="nameless@example.com",
    )

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    assert document.xpath('//input[@aria-label="Select nameless@example.com"]')


@pytest.mark.django_db
def test_a_nameless_learners_page_names_them_by_email_in_its_document_title(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(
        organisation=organisation,
        first_name="",
        last_name="",
        email="nameless@example.com",
    )

    response = role_holder_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    document = lxml.html.fromstring(response.content.decode())
    assert "nameless@example.com" in document.xpath("//title")[0].text_content()


@pytest.mark.django_db
def test_learners_list_empty_cohorts_and_courses_cells_read_the_same_em_dash(
    role_holder_client,
):
    """A learner with no cohort and no registration used to show an em dash in
    Cohorts but a plain hyphen in Courses."""
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)

    response = role_holder_client(organisation).get(_learners_url(organisation.slug))

    document = lxml.html.fromstring(response.content.decode())
    dashes = document.xpath("//td//span[@role='img'][@aria-label='None']")
    assert len(dashes) >= 2
    assert {dash.text_content().strip() for dash in dashes} == {"—"}
    for cell in document.xpath("//tbody//td"):
        assert cell.text_content().strip() != "-"


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
