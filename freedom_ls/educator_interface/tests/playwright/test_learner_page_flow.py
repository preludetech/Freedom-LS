"""The educator's learner journey: the learners list, a learner's page and its
Courses tab, with a layout check at every QA viewport."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_opening_a_learner_and_their_courses_tab(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="Ada",
        user__last_name="Lovelace",
        user__email="ada@example.com",
    )
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    list_url = page.url
    page.get_by_role("link", name="Ada Lovelace").first.click()

    expect(page.locator("#instance-title")).to_have_text("Ada Lovelace")
    expect(page.get_by_text("ada@example.com").first).to_be_visible()
    page.get_by_role("link", name="Courses", exact=True).click()
    expect(page.get_by_text("Algebra")).to_be_visible()
    expect(page.get_by_text("Never")).to_be_visible()
    learner_url = page.url

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(list_url)
        assert_no_horizontal_overflow(page)
        page.goto(learner_url)
        assert_no_horizontal_overflow(page)


def test_deactivating_then_reactivating_a_learner_from_the_page_header(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="Ada",
        user__last_name="Lovelace",
    )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisation.slug, f"learners/{learner.pk}"))
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("button", name="Deactivate", exact=True).first.click()
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Removed", exact=True).first).to_be_visible()
    main.get_by_role("button", name="Reactivate", exact=True).first.click()
    modal.get_by_role("button", name="Reactivate", exact=True).click()
    expect(modal).to_be_hidden()
    expect(main.get_by_text("Active", exact=True).first).to_be_visible()
