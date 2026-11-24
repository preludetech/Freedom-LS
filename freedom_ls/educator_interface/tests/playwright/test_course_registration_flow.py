"""E2E Playwright journeys for registering and deactivating from a course's
Overview tab.

Which registrations change, and the headers and audit entries that follow,
are covered by tests/panels/course/test_actions.py. What only a browser shows
is the panel refreshing in place, with no page navigation.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_deactivating_a_cohort_registration_from_the_course_overview(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    course = CourseFactory(title="Algebra")
    cohort = CohortFactory(organisation=organisation, name="Cohort A")
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisation.slug, f"courses/{course.pk}"))
    modal = page.locator("#app-modal")
    panel = page.locator("section[data-panel='cohorts']")
    row = panel.get_by_role("row").filter(has_text="Cohort A")
    page.evaluate("window.__noReload = true")

    row.get_by_role("button", name="Deactivate Cohort A").click()
    modal.get_by_label("Reason").fill("Course retired")
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_text("Inactive", exact=True)).to_be_visible()
    expect(row.get_by_role("button", name="Deactivate Cohort A")).to_have_count(0)
    assert page.evaluate("window.__noReload") is True
