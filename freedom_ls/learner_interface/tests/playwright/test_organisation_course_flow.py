"""Browser flow for a learner whose organisation publishes a course that shares
its title with another organisation's course."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import CourseAudience, DifficultyLevel, PriceKind
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

SHARED_TITLE = "Workplace Safety Essentials"


def test_learner_sees_only_their_organisations_course_with_its_byline(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    own = OrganisationFactory(name="Harbour College")
    other = OrganisationFactory(name="Northwind Logistics")
    own_course = CourseFactory(
        title=SHARED_TITLE,
        slug="safety-harbour",
        audience=CourseAudience.ORGANISATION_LEARNERS,
        access_config={"access_type": "free"},
    )
    own_course.organisations.add(own)
    other_course = CourseFactory(
        title=SHARED_TITLE,
        slug="safety-northwind",
        audience=CourseAudience.ORGANISATION_LEARNERS,
        access_config={"access_type": "free"},
    )
    other_course.organisations.add(other)
    ContentCollectionItemFactory(
        collection_object=own_course,
        child_object=TopicFactory(title="Safety on site", slug="safety-on-site"),
        order=0,
    )
    LearnerCourseRegistrationFactory(
        learner__user=logged_in_user,
        learner__organisation=own,
        course=own_course,
        is_active=True,
    )

    page.goto(str(reverse_url(live_server, "learner_interface:dashboard")))

    expect(page.get_by_role("link", name=SHARED_TITLE, exact=True)).to_have_count(1)
    expect(page.get_by_text("Harbour College").first).to_be_visible()
    expect(page.get_by_text("Northwind Logistics")).to_have_count(0)

    response = page.goto(
        str(
            reverse_url(
                live_server,
                "learner_interface:course_detail",
                kwargs={"course_slug": other_course.slug},
            )
        )
    )
    assert response is not None
    assert response.status == 404

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(str(reverse_url(live_server, "learner_interface:dashboard")))
        expect(page.get_by_role("link", name=SHARED_TITLE, exact=True)).to_have_count(1)
        expect(
            page.get_by_text("Harbour College").locator("visible=true")
        ).to_be_visible()
        assert_no_horizontal_overflow(page)


def test_clicking_the_card_byline_opens_the_course(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    """The byline overlaps the card header above the stretched title link; it
    used to sit on top of the link and swallow every click on its strip."""
    page = logged_in_page
    organisation = OrganisationFactory(name="Harbour College")
    course = CourseFactory(
        title="Clickable Card",
        slug="clickable-card",
        audience=CourseAudience.ORGANISATION_LEARNERS,
        access_config={"access_type": "free"},
    )
    course.organisations.add(organisation)
    LearnerCourseRegistrationFactory(
        learner__user=logged_in_user,
        learner__organisation=organisation,
        course=course,
        is_active=True,
    )

    page.goto(str(reverse_url(live_server, "learner_interface:dashboard")))
    # The phone-width row is in the DOM too, hidden; the card is the visible one.
    card = page.locator("article.course-card", has_text="Clickable Card").locator(
        "visible=true"
    )
    target = card.get_by_role("link", name="Clickable Card", exact=True).get_attribute(
        "href"
    )
    assert target is not None

    # A pointer click at the name's position: the stretched link overlays the
    # byline, so an element click would be refused as intercepted.
    box = card.get_by_text("Harbour College").bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    # The course home then sends the learner on to their first item.
    expect(page).to_have_url(re.compile(f"^{re.escape(live_server.url + target)}"))


# Each chip's box, the difficulty's box and the byline name's width, read from
# the first row on the page.
ROW_EYEBROW_GEOMETRY = """() => {
    const row = document.querySelector('article.course-card');
    const line = row.querySelector('div.flex.items-start.justify-between');
    const rect = (el) => el.getBoundingClientRect();
    const chips = [...line.lastElementChild.children].map(rect);
    const difficulty = [...line.querySelectorAll('span')].find(
        (s) => s.textContent.trim() === 'BEGINNER' || s.textContent.trim() === 'Beginner'
    );
    const name = line.querySelector('[data-testid="organisation-byline"] span.truncate');
    return {
        articleOverflow: row.scrollWidth - row.clientWidth,
        lineRight: rect(line).right,
        chips: chips.map((r) => ({left: r.left, right: r.right, top: r.top, bottom: r.bottom})),
        difficulty: (() => { const r = rect(difficulty); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom}; })(),
        nameWidth: rect(name).width,
    };
}"""


def test_row_eyebrow_chips_wrap_without_overlapping_or_clipping_on_a_phone(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    """A phone-width row's price and status chips used to stay on one line,
    overlapping the difficulty, running past the card edge and squeezing the
    organisation name to nothing."""
    page = logged_in_page
    organisation = OrganisationFactory(name="Skyline Aviation")
    course = CourseFactory(
        title="Row With Many Chips",
        slug="row-with-many-chips",
        audience=CourseAudience.ORGANISATION_LEARNERS,
        access_config={"access_type": "free"},
        difficulty=DifficultyLevel.BEGINNER,
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.00"),
        price_sale_amount=Decimal("999.00"),
        price_currency="ZAR",
    )
    course.organisations.add(organisation)
    LearnerCourseRegistrationFactory(
        learner__user=logged_in_user,
        learner__organisation=organisation,
        course=course,
        is_active=True,
    )
    page.set_viewport_size({"width": 375, "height": 812})

    page.goto(str(reverse_url(live_server, "learner_interface:courses")))
    geometry = page.evaluate(ROW_EYEBROW_GEOMETRY)

    assert geometry["articleOverflow"] <= 0
    assert geometry["nameWidth"] > 0
    assert all(chip["right"] <= geometry["lineRight"] + 1 for chip in geometry["chips"])
    difficulty = geometry["difficulty"]
    assert all(
        chip["left"] >= difficulty["right"]
        or chip["top"] >= difficulty["bottom"]
        or chip["bottom"] <= difficulty["top"]
        for chip in geometry["chips"]
    )
