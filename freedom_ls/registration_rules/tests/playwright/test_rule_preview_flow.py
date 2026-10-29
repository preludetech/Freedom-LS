"""A person enables a registration rule in the admin and confirms the preview."""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    LearnerHRAttributesFactory,
    OrganisationHRSettingsFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def admin_user(db, live_server_site, mock_site_context):
    """A fresh, email-verified superuser."""
    user = UserFactory(superuser=True, password=_LOGGED_IN_PASSWORD)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


@pytest.fixture
def admin_page(page: Page, live_server, admin_user) -> Page:
    """A Playwright Page logged in as admin_user."""
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)
    return page


def _pick_autocomplete(page: Page, label: str, text: str) -> None:
    """Choose an entry in an admin autocomplete (select2) field."""
    page.locator(f"#id_{label}").locator("xpath=following-sibling::span").click()
    page.locator(".select2-search__field").fill(text)
    page.get_by_role("option", name=text).click()


def test_enabling_a_rule_previews_then_registers_the_matching_learner(
    live_server, admin_page: Page, live_server_site
) -> None:
    # Arrange
    organisation = OrganisationFactory(name="Acme Finance")
    OrganisationHRSettingsFactory(
        organisation=organisation, registration_rules_enabled=True
    )
    CourseFactory(title="Budgeting basics")
    department = DepartmentFactory(organisation=organisation, name="Accounts")
    learner = LearnerHRAttributesFactory(
        learner__organisation=organisation,
        learner__user__first_name="Maya",
        department=department,
    ).learner
    page = admin_page
    departments = page.locator("#id_attribute_conditions-0-departments")

    # Act
    page.goto(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_registration_rules_registrationrule_add')}"
    )
    page.get_by_label("Name").fill("Accounts team")
    _pick_autocomplete(page, "organisation", "Acme Finance")
    _pick_autocomplete(page, "course", "Budgeting basics")
    page.get_by_role("button", name="Save", exact=True).first.click()

    departments.select_option(label="Accounts")
    page.get_by_label("Is enabled").check()
    page.get_by_role("button", name="Save", exact=True).first.click()

    # Assert: the preview names the learner and nothing is saved yet.
    expect(page.get_by_text("Will be registered (1)")).to_be_visible()
    expect(page.get_by_text(str(learner.user.email))).to_be_visible()

    # Act: back to the form.
    page.get_by_role("link", name="Back to the form").click()

    # Assert: the submitted values are still in the form.
    expect(page.get_by_label("Is enabled")).to_be_checked()
    expect(departments).to_have_values([str(department.pk)])

    # Act: save again and confirm.
    page.get_by_role("button", name="Save", exact=True).first.click()
    page.get_by_role("button", name="Confirm and save").click()
    expect(page).to_have_url(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_registration_rules_registrationrule_changelist')}"
    )

    # Assert: the learner's registration names the rule.
    page.goto(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_learner_management_learnercourseregistration_changelist')}"
    )
    page.get_by_role("link", name="Maya", exact=True).click()
    expect(page.get_by_role("link", name="Accounts team")).to_be_visible()

    # Assert: the preview fits every viewport.
    page.goto(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_registration_rules_registrationrule_changelist')}"
    )
    page.get_by_role("link", name="Accounts team").click()
    page.get_by_label("Is enabled").uncheck()
    page.get_by_role("button", name="Save", exact=True).first.click()
    expect(page.get_by_text("Will be retracted (1)")).to_be_visible()
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)


def test_a_recommend_rule_shows_the_course_as_recommended_until_the_learner_registers(
    live_server, admin_page: Page, live_server_site
) -> None:
    # Arrange
    organisation = OrganisationFactory(name="Acme Finance")
    OrganisationHRSettingsFactory(
        organisation=organisation, registration_rules_enabled=True
    )
    course = CourseFactory(title="Budgeting basics")
    department = DepartmentFactory(organisation=organisation, name="Accounts")
    learner_user = UserFactory(password=_LOGGED_IN_PASSWORD)
    EmailAddress.objects.create(
        user=learner_user, email=learner_user.email, verified=True, primary=True
    )
    LearnerHRAttributesFactory(
        learner__organisation=organisation,
        learner__user=learner_user,
        department=department,
    )
    page = admin_page

    # Act: staff make an enabled recommend rule and confirm its preview.
    page.goto(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_registration_rules_registrationrule_add')}"
    )
    page.get_by_label("Name").fill("Accounts team")
    _pick_autocomplete(page, "organisation", "Acme Finance")
    _pick_autocomplete(page, "course", "Budgeting basics")
    page.get_by_label("Recommend", exact=True).check()
    page.get_by_role("button", name="Save", exact=True).first.click()

    page.locator("#id_attribute_conditions-0-departments").select_option(
        label="Accounts"
    )
    page.get_by_label("Is enabled").check()
    page.get_by_role("button", name="Save", exact=True).first.click()

    # Assert
    expect(page.get_by_text("Will be recommended (1)")).to_be_visible()
    expect(page.get_by_text(str(learner_user.email))).to_be_visible()

    # Act
    page.get_by_role("button", name="Confirm and save").click()
    expect(page).to_have_url(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_registration_rules_registrationrule_changelist')}"
    )

    # Act: the learner opens the dashboard.
    page.context.clear_cookies()
    _login_via_ui(page, live_server, str(learner_user.email), _LOGGED_IN_PASSWORD)
    dashboard = f"{live_server.url}{reverse('learner_interface:dashboard')}"
    page.goto(dashboard)

    # Assert
    expect(
        page.locator("#recommended-courses")
        .get_by_test_id("section-card-grid")
        .get_by_text(course.title, exact=True)
    ).to_be_visible()

    # Act: the learner registers for the course.
    page.goto(
        f"{live_server.url}"
        f"{reverse('learner_interface:initiate_course_access', args=[course.slug])}"
    )
    page.goto(dashboard)

    # Assert
    expect(page.get_by_text(course.title, exact=True).first).to_be_visible()
    expect(
        page.locator("#recommended-courses").get_by_text(course.title, exact=True)
    ).to_have_count(0)
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
