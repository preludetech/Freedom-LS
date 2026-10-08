"""E2E Playwright test for registering a cohort for a course and unregistering
it again from the cohort's Courses tab.

The registration state changes and headers are covered by test_actions.py.
What only a browser shows is the row appearing and flipping badge after the
page navigates, the tab count following, and the Register dialog offering the
course again.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_registering_then_unregistering_a_cohort_from_the_courses_tab(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    CourseFactory(title="Algebra")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(
        interface_url(
            live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"
        )
    )
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("button", name="Register", exact=True).click()
    modal.get_by_label("Course").select_option(label="Algebra")
    modal.get_by_role("button", name="Register", exact=True).click()

    expect(modal).to_be_hidden()
    row = main.get_by_role("row").filter(has_text="Algebra")
    expect(row.get_by_text("Active", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Courses 1", exact=True)).to_be_visible()

    row.get_by_role("button", name="Unregister", exact=True).click()
    modal.get_by_role("button", name="Unregister", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_text("Inactive", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Courses 0", exact=True)).to_be_visible()
    main.get_by_role("button", name="Register", exact=True).click()
    expect(
        modal.get_by_label("Course").locator("option", has_text="Algebra")
    ).to_have_count(1)
