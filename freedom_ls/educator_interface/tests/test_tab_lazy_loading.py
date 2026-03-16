"""Playwright E2E test: tab lazy-loading via HTMX works with Alpine CSP build."""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from guardian.shortcuts import assign_perm
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_management.factories import CohortFactory


@pytest.fixture
def _educator_user(db, live_server_site, mock_site_context) -> tuple:
    """Create a staff user with verified email. Returns (user, password)."""
    password = "testpass"  # noqa: S105  # pragma: allowlist secret
    user = UserFactory(password=password, staff=True)
    EmailAddress.objects.get_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user, password


@pytest.fixture
def educator_page(
    page: Page, live_server, _educator_user: tuple
) -> tuple[Page, object]:
    """Staff user logged in via Playwright. Returns (page, user)."""
    user, password = _educator_user
    login_url = f"{live_server.url}{reverse('account_login')}"
    page.goto(login_url)
    page.fill('input[name="login"]', str(user.email))
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    return page, user


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_details_tab_lazy_loads_content(
    educator_page: tuple[Page, object], live_server
) -> None:
    """Clicking 'Details' tab triggers HTMX lazy-load and renders tab content."""
    page, user = educator_page
    cohort = CohortFactory()
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)

    cohort_url = f"{live_server.url}{reverse('educator_interface:interface', kwargs={'path_string': f'cohorts/{cohort.pk}'})}"
    page.goto(cohort_url)
    page.wait_for_load_state("networkidle")

    # Click the "Details" tab button and wait for HTMX lazy-load
    details_button = page.locator('button[data-tab-name="details"]')
    expect(details_button).to_be_visible()
    details_button.click()
    page.wait_for_load_state("networkidle")

    # The details tab panel should be visible with loaded content
    details_panel = page.locator("#tab-content-details:not([hidden])")
    expect(details_panel).to_be_visible()

    # The panel should contain the "Name" field from CohortDetailsPanel (desktop table layout)
    expect(details_panel.locator("th", has_text="Name").first).to_be_visible(
        timeout=5000
    )


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_details_panel_refreshes_after_edit(
    educator_page: tuple[Page, object], live_server
) -> None:
    """After editing cohort via modal, the details panel refreshes to show updated data."""
    page, user = educator_page
    cohort = CohortFactory(name="Original Name")
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    assign_perm("freedom_ls_student_management.change_cohort", user, cohort)

    cohort_url = f"{live_server.url}{reverse('educator_interface:interface', kwargs={'path_string': f'cohorts/{cohort.pk}'})}"
    page.goto(cohort_url)
    page.wait_for_load_state("networkidle")

    # Click the "Details" tab to lazy-load it
    details_button = page.locator('button[data-tab-name="details"]')
    details_button.click()
    page.wait_for_load_state("networkidle")

    # Wait for details panel to be visible and loaded
    details_panel = page.locator("#tab-content-details:not([hidden])")
    expect(details_panel).to_be_visible(timeout=5000)
    expect(details_panel.locator("td", has_text="Original Name").first).to_be_visible(
        timeout=5000
    )

    # Click the Edit button to open modal
    details_panel.locator("button", has_text="Edit").click()
    modal = page.locator('[x-data="modal"]')
    expect(modal).to_be_visible(timeout=5000)

    # Fill in the new name and submit within the modal
    modal.locator('input[name="name"]').fill("Updated Name")
    modal.locator('button[type="submit"]').click()
    page.wait_for_load_state("networkidle")

    # The details panel should show the updated name WITHOUT a page reload
    details_panel = page.locator("#tab-content-details:not([hidden])")
    expect(details_panel.locator("td", has_text="Updated Name").first).to_be_visible(
        timeout=5000
    )

    # The page heading (h1) should also update to the new name
    heading = page.locator("#instance-title")
    expect(heading).to_have_text("Updated Name", timeout=5000)
