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
from freedom_ls.tests.playwright_helpers import QA_VIEWPORTS

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
