"""Browser flow for a learner whose organisation publishes a course that shares
its title with another organisation's course."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import CourseAudience
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

    expect(page.get_by_role("link", name=SHARED_TITLE)).to_have_count(1)
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
        expect(page.get_by_role("link", name=SHARED_TITLE)).to_have_count(1)
        expect(
            page.get_by_text("Harbour College").locator("visible=true")
        ).to_be_visible()
        assert_no_horizontal_overflow(page)
