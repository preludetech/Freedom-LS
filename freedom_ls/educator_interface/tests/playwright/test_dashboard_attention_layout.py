"""The dashboard's Needs attention rows in a real browser."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_canvas_holds_only_boxes,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_attention_row_avatar_stays_level_with_the_name_on_a_multi_line_row(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """The avatar used to be centred on the whole row, so a row with cohort
    detail under the name left it well below the name."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Dashboard Org")
    cohort = CohortFactory(organisation=organisation, name="Flagged Cohort")
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    CohortMembershipFactory(
        cohort=cohort,
        learner__user=UserFactory(first_name="Thandi", last_name="Mokoena"),
    )
    assign_object_role(educator_user, organisation, "organisation_admin")
    dashboard_url = interface_url(live_server, organisation.slug, "dashboard")

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(dashboard_url)
        link = page.get_by_role("link", name="Thandi Mokoena", exact=True)
        expect(link).to_be_visible()
        name = link.get_by_text("Thandi Mokoena", exact=True)
        row = page.locator("li", has=link).last
        avatar = row.locator("[class*='panel-avatar-']").first
        name_box = name.bounding_box()
        avatar_box = avatar.bounding_box()
        assert name_box is not None
        assert avatar_box is not None
        name_mid = name_box["y"] + name_box["height"] / 2
        avatar_mid = avatar_box["y"] + avatar_box["height"] / 2
        assert abs(avatar_mid - name_mid) <= 6, viewport


def test_the_dashboard_canvas_holds_only_boxes(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
    settings,
) -> None:
    """The figures date and the over-limit notice used to sit on the canvas,
    between the stat tiles and the cards."""
    settings.REPORTS_MAX_LEARNERS = 1
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Dashboard Org")
    big = CohortFactory(organisation=organisation, name="Big Cohort")
    small = CohortFactory(organisation=organisation, name="Small Cohort")
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    for cohort, count in ((big, 2), (small, 1)):
        CohortCourseRegistrationFactory(cohort=cohort, course=course)
        for _ in range(count):
            CohortMembershipFactory(cohort=cohort)
    assign_object_role(educator_user, organisation, "organisation_admin")

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(interface_url(live_server, organisation.slug, "dashboard"))
        progress = page.get_by_role("region", name="Cohort progress")
        notice = progress.locator("[data-excluded-cohort]")
        expect(notice).to_contain_text("Big Cohort has 2 learners")
        expect(progress.get_by_text("Figures as of")).to_be_visible()
        expect(
            page.get_by_role("region", name="Needs attention").get_by_text(
                "Figures as of"
            )
        ).to_be_visible()
        assert_canvas_holds_only_boxes(page)


def test_a_dashboard_with_no_cohorts_holds_only_boxes(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Empty Org")
    assign_object_role(educator_user, organisation, "organisation_admin")

    page.goto(interface_url(live_server, organisation.slug, "dashboard"))

    expect(page.get_by_text("You have no cohorts yet.")).to_be_visible()
    assert_canvas_holds_only_boxes(page)


_HIT_AREA = """(link) => {
    const box = link.getBoundingClientRect();
    const after = getComputedStyle(link, "::after");
    const height = after.content === "none" ? 0 : parseFloat(after.height) || 0;
    const x = box.left + box.width / 2;
    const centre = box.top + box.height / 2;
    // What a finger lands on 20px above and below the link's centre.
    const hit = (y) => document.elementFromPoint(x, y)?.closest("a") === link;
    return {
        height: Math.max(box.height, height),
        topHit: hit(centre - 20),
        bottomHit: hit(centre + 20),
        left: box.left,
        right: box.right,
    };
}"""


def test_attention_cohort_name_has_a_44px_hit_area_clear_of_its_quick_view_icon(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """On a phone a cohort name in a Needs attention row was only as tall as
    its text, with no hit area, while the course names beside it are inline
    text and stay exempt."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Dashboard Org")
    cohort = CohortFactory(organisation=organisation, name="Flagged Cohort")
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    CohortMembershipFactory(
        cohort=cohort,
        learner__user=UserFactory(first_name="Thandi", last_name="Mokoena"),
    )
    assign_object_role(educator_user, organisation, "organisation_admin")
    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(interface_url(live_server, organisation.slug, "dashboard"))

    attention = page.get_by_role("region", name="Needs attention")
    name_link = attention.get_by_role("link", name="Flagged Cohort", exact=True)
    expect(name_link).to_be_visible()
    area = name_link.evaluate(_HIT_AREA)
    assert area["height"] >= 44, area
    assert area["topHit"], "the cohort name's hit area does not reach 20px above it"
    assert area["bottomHit"], "the cohort name's hit area does not reach 20px below it"

    quick_view = attention.get_by_label("Quick view: Flagged Cohort")
    icon = quick_view.bounding_box()
    assert icon is not None
    assert area["right"] <= icon["x"], (
        "the name's hit area overlaps its quick view icon"
    )
