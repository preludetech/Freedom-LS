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
    LearnerCourseRegistrationFactory,
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


def test_registering_a_cohort_from_the_course_overview_and_again_after_deactivating(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    course = CourseFactory(title="Algebra")
    CohortFactory(organisation=organisation, name="Cohort A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisation.slug, f"courses/{course.pk}"))
    modal = page.locator("#app-modal")
    panel = page.locator("section[data-panel='cohorts']")
    row = panel.get_by_role("row").filter(has_text="Cohort A")
    page.evaluate("window.__noReload = true")

    panel.get_by_role("button", name="Register", exact=True).click()
    modal.get_by_label("Cohort").select_option(label="Cohort A")
    modal.get_by_role("button", name="Register", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_role("button", name="Deactivate Cohort A")).to_be_visible()

    row.get_by_role("button", name="Deactivate Cohort A").click()
    modal.get_by_label("Reason").fill("Course retired")
    modal.get_by_role("button", name="Deactivate", exact=True).click()
    expect(row.get_by_text("Inactive", exact=True)).to_be_visible()

    panel.get_by_role("button", name="Register", exact=True).click()
    modal.get_by_label("Cohort").select_option(label="Cohort A")
    modal.get_by_role("button", name="Register", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row).to_have_count(1)
    expect(row.get_by_role("button", name="Deactivate Cohort A")).to_be_visible()
    assert page.evaluate("window.__noReload") is True


def test_deactivating_and_reactivating_a_direct_registration_from_the_course_overview(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    course = CourseFactory(title="Algebra")
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    LearnerCourseRegistrationFactory(learner=learner, course=course)
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisation.slug, f"courses/{course.pk}"))
    modal = page.locator("#app-modal")
    panel = page.locator("section[data-panel='learners']")
    row = panel.get_by_role("row").filter(has_text="Ada Lovelace")
    name = learner.user.display_name
    page.evaluate("window.__noReload = true")

    row.get_by_role("button", name=f"Deactivate {name}").click()
    modal.get_by_label("Reason").fill("Left the programme")
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_role("button", name=f"Reactivate {name}")).to_be_visible()
    expect(row.get_by_role("button", name=f"Deactivate {name}")).to_have_count(0)

    row.get_by_role("button", name=f"Reactivate {name}").click()
    modal.get_by_role("button", name="Reactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_role("button", name=f"Deactivate {name}")).to_be_visible()
    assert page.evaluate("window.__noReload") is True


def test_registering_a_learner_from_the_course_overview(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    course = CourseFactory(title="Algebra")
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Test"
    )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisation.slug, f"courses/{course.pk}"))
    modal = page.locator("#app-modal")
    panel = page.locator("section[data-panel='learners']")
    row = panel.get_by_role("row").filter(has_text=learner.user.display_name)
    page.evaluate("window.__noReload = true")

    panel.get_by_role("button", name="Register", exact=True).click()
    modal.get_by_label("Learner").select_option(label=learner.user.display_name)
    modal.get_by_role("button", name="Register", exact=True).click()

    expect(modal).to_be_hidden()
    expect(
        row.get_by_role("button", name=f"Deactivate {learner.user.display_name}")
    ).to_be_visible()
    assert page.evaluate("window.__noReload") is True
