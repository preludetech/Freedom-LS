"""The educator dashboard: a base view with no instance and no table."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import timedelta
from typing import cast

import lxml.html
import pytest

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.http import HttpResponse
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.educator_interface.reporting import gathered_figures
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.reports.report_data import ATTENTION_LIST_MAX
from freedom_ls.reports.tests.helpers import topic_progress
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _empty_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def educator(mock_site_context: Site) -> tuple[Organisation, AbstractBaseUser]:
    organisation: Organisation = OrganisationFactory(name="Northside Academy")
    user: AbstractBaseUser = UserFactory(staff=True)
    assign_object_role(user, organisation, "organisation_admin")
    return organisation, user


def _dashboard_url(organisation: Organisation) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "dashboard"},
    )


def _load_region(client: Client, organisation: Organisation) -> HttpResponse:
    """The fetch the skeleton fires: the dashboard's own region with loaded=1."""
    url = _dashboard_url(organisation)
    region_id = "panel-" + re.sub(r"[^\w-]+", "-", url).strip("-")
    return cast(
        HttpResponse,
        client.get(
            url, {"loaded": "1"}, HTTP_HX_REQUEST="true", HTTP_HX_TARGET=region_id
        ),
    )


def _tiles(response: HttpResponse) -> dict[str, str]:
    """Each stat tile's label mapped to its value text."""
    document = lxml.html.fromstring(response.content.decode())
    return {
        dl.xpath("string(dt)").strip(): dl.xpath("string(dd[1])").strip()
        for dl in document.xpath("//dl[dt]")
    }


def _members(cohort: Cohort, last_names: list[str]) -> list:
    return [
        CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(first_name="Learner", last_name=last_name),
        ).learner
        for last_name in last_names
    ]


def _finish_topic(course, learner, days_ago: int = 0) -> None:
    topic = course.items.get().child
    record = course_progress_record(course, learner.user)
    topic_progress(
        record, topic, complete_time=timezone.now() - timedelta(days=days_ago)
    )


def _course_with_topic():
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    return course


def _grant(user: AbstractBaseUser, role: str, target) -> AbstractBaseUser:
    assign_object_role(user, target, role)
    return user


@pytest.fixture
def scoped_organisation(mock_site_context: Site):
    """Cohort A (2 learners) and cohort B (3), plus a cohort of another site (4)."""
    organisation: Organisation = OrganisationFactory()
    cohort_a = CohortFactory(organisation=organisation, name="Visible A")
    cohort_b = CohortFactory(organisation=organisation, name="Hidden B")
    _members(cohort_a, ["Alpha", "Bravo"])
    _members(cohort_b, ["Charlie", "Delta", "Echo"])
    other_site = SiteFactory()
    other_cohort = CohortFactory(site=other_site, name="Other site")
    CohortMembershipFactory.create_batch(4, cohort=other_cohort, site=other_site)
    return organisation, cohort_a


@pytest.mark.django_db
def test_the_page_renders_the_four_tile_labels_and_two_skeleton_tiles(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, user = educator
    _members(CohortFactory(organisation=organisation), ["Alpha"])

    response = logged_in_client(user).get(_dashboard_url(organisation))

    content = response.content.decode()
    document = lxml.html.fromstring(content)
    assert list(_tiles(response)) == [
        "Learners",
        "Cohorts",
        "Average progress",
        "Learners needing attention",
    ]
    assert len(document.xpath("//dl//div[@data-skeleton-line]")) == 2
    assert "arrives in a later release" not in content


@pytest.mark.django_db
def test_the_loaded_fetch_fills_the_two_lazy_tiles(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, user = educator
    _members(CohortFactory(organisation=organisation), ["Alpha", "Bravo"])

    response = _load_region(logged_in_client(user), organisation)

    document = lxml.html.fromstring(response.content.decode())
    assert _tiles(response)["Learners needing attention"] == "2"
    assert len(document.xpath("//dl//div[@data-skeleton-line]")) == 0
    assert "Figures as of" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "learners", "cohorts"),
    [
        ("organisation_admin", "5", "2"),
        ("cohort_admin", "2", "1"),
        ("cohort_viewer", "2", "1"),
    ],
)
def test_every_figure_covers_only_the_cohorts_the_role_can_see(
    scoped_organisation, logged_in_client, role: str, learners: str, cohorts: str
) -> None:
    organisation, cohort_a = scoped_organisation
    target = organisation if role == "organisation_admin" else cohort_a
    user = _grant(UserFactory(staff=True), role, target)
    client = logged_in_client(user)

    inline = _tiles(client.get(_dashboard_url(organisation)))
    loaded = _tiles(_load_region(client, organisation))

    assert (inline["Learners"], inline["Cohorts"]) == (learners, cohorts)
    assert loaded["Learners needing attention"] == learners


@pytest.mark.django_db
def test_the_attention_tile_counts_every_flagged_learner_beyond_the_list_cap(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, user = educator
    cohort = CohortFactory(organisation=organisation)
    _members(cohort, [f"Learner{n:02d}" for n in range(15)])

    response = _load_region(logged_in_client(user), organisation)

    document = lxml.html.fromstring(response.content.decode())
    assert ATTENTION_LIST_MAX == 12
    assert _tiles(response)["Learners needing attention"] == "15"
    assert len(document.xpath("//button[@aria-controls='quick-view']")) == 12
    assert "Showing 12 of 15 learners flagged." in response.content.decode()


@pytest.fixture
def shared_learner(mock_site_context: Site):
    """One learner in two cohorts: 100% but inactive for 10 days in one, 0% in the other."""
    organisation: Organisation = OrganisationFactory()
    course_a, course_b = _course_with_topic(), _course_with_topic()
    cohort_a = CohortFactory(organisation=organisation, name="First")
    cohort_b = CohortFactory(organisation=organisation, name="Second")
    CohortCourseRegistrationFactory(cohort=cohort_a, course=course_a)
    CohortCourseRegistrationFactory(cohort=cohort_b, course=course_b)
    (learner,) = _members(cohort_a, ["Shared"])
    CohortMembershipFactory(cohort=cohort_b, learner=learner)
    _finish_topic(course_a, learner, days_ago=10)
    return organisation, [cohort_a, cohort_b]


@pytest.mark.django_db
def test_a_learner_in_two_cohorts_counts_once_at_the_mean_of_their_completions(
    shared_learner,
) -> None:
    _organisation, cohorts = shared_learner

    figures = gathered_figures(cohorts)

    assert figures.average_progress == 50
    assert figures.attention_count == 1
    assert [len(row.cohorts) for row in figures.attention_rows] == [2]
    assert figures.attention_rows[0].lowest_completion == 0


@pytest.mark.django_db
def test_attention_rows_order_by_lowest_completion_then_sort_key(
    mock_site_context: Site,
) -> None:
    course = _course_with_topic()
    cohort = cast(Cohort, CohortFactory())
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    zero_progress = _members(cohort, ["Baker", "Able"])
    (finished,) = _members(cohort, ["Aaron"])
    _finish_topic(course, finished, days_ago=10)

    figures = gathered_figures([cohort])

    assert len(zero_progress) == 2
    assert [row.full_name for row in figures.attention_rows] == [
        "Learner Able",
        "Learner Baker",
        "Learner Aaron",
    ]


@pytest.mark.django_db
def test_cohort_rows_order_by_lowest_mean_then_name_with_an_empty_cohort_last(
    mock_site_context: Site,
) -> None:
    organisation: Organisation = OrganisationFactory()
    course = _course_with_topic()
    zulu = CohortFactory(organisation=organisation, name="Zulu")
    CohortCourseRegistrationFactory(cohort=zulu, course=course)
    (finisher,) = _members(zulu, ["Done"])
    _finish_topic(course, finisher)
    cohorts = [
        zulu,
        CohortFactory(organisation=organisation, name="Empty"),
        CohortFactory(organisation=organisation, name="Bravo"),
        CohortFactory(organisation=organisation, name="Alpha"),
    ]
    _members(cohorts[2], ["One"])
    _members(cohorts[3], ["Two"])

    figures = gathered_figures(cohorts)

    assert [row.cohort.name for row in figures.cohort_rows] == [
        "Alpha",
        "Bravo",
        "Zulu",
        "Empty",
    ]
    assert [row.mean_completion for row in figures.cohort_rows] == [0, 0, 100, None]


@pytest.mark.django_db
@override_settings(REPORTS_MAX_LEARNERS=2)
def test_an_over_limit_cohort_is_counted_inline_and_named_in_a_notice(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, user = educator
    _members(CohortFactory(organisation=organisation, name="Big"), ["A", "B", "C"])
    _members(CohortFactory(organisation=organisation, name="Small"), ["D"])
    client = logged_in_client(user)

    inline = _tiles(client.get(_dashboard_url(organisation)))
    loaded = _load_region(client, organisation)

    assert (inline["Learners"], inline["Cohorts"]) == ("4", "2")
    assert _tiles(loaded)["Learners needing attention"] == "1"
    assert (
        "Big has 3 learners, over the report limit of 2, and is not included"
        in loaded.content.decode()
    )


@pytest.mark.django_db
def test_an_organisation_admin_with_no_cohorts_is_invited_to_make_one(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, user = educator

    response = logged_in_client(user).get(_dashboard_url(organisation))

    content = response.content.decode()
    assert "You have no cohorts yet" in content
    assert "Learners needing attention" not in content


@pytest.mark.django_db
def test_a_cohort_role_with_no_active_cohort_is_told_none_are_assigned(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, _admin = educator
    inactive = CohortFactory(organisation=organisation, is_active=False)
    user = _grant(UserFactory(staff=True), "cohort_viewer", inactive)

    response = logged_in_client(user).get(_dashboard_url(organisation))

    assert "No cohorts are assigned to you" in response.content.decode()


@pytest.mark.django_db
def test_an_empty_cohort_loads_with_a_dash_for_average_progress(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, user = educator
    CohortFactory(organisation=organisation)

    response = _load_region(logged_in_client(user), organisation)

    assert response.status_code == 200
    assert _tiles(response)["Average progress"] == "\u2014"
    assert "Nobody needs attention right now" in response.content.decode()


@pytest.mark.django_db
def test_an_attention_row_has_one_learner_link_and_a_named_quick_view_trigger(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, user = educator
    (learner,) = _members(CohortFactory(organisation=organisation), ["Alpha"])
    learner_path = reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation.slug,
            "path_string": f"learners/{learner.pk}",
        },
    )

    response = _load_region(logged_in_client(user), organisation)

    document = lxml.html.fromstring(response.content.decode())
    (row,) = document.xpath("//li[.//button[@aria-controls='quick-view']]")
    (button,) = row.xpath(".//button[@aria-controls='quick-view']")
    assert len(row.xpath(f".//a[@href='{learner_path}']")) == 1
    assert button.get("aria-label") == "Quick view: Learner Alpha"
    assert button.get("hx-get") == f"{learner_path}/__quick-view"


@pytest.mark.django_db
def test_the_bare_root_redirects_to_the_dashboard(
    educator: tuple[Organisation, AbstractBaseUser],
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    organisation, user = educator

    response = logged_in_client(user).get(reverse("educator_interface:root"))

    assert response["Location"] == reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "dashboard"},
    )
