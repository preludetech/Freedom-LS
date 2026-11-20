"""Withdrawing an application through the confirm dialog, in a real browser.

Focus handling, the Tab trap and Escape are browser behaviour that no pytest
client test can prove.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.conftest import reverse_url
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_an_applicant_withdraws_a_submitted_application_through_the_dialog(
    live_server, logged_in_page: Page, logged_in_user, mock_site_context
):
    application = CourseApplicationFactory(user=logged_in_user)
    logged_in_page.goto(
        reverse_url(
            live_server, "course_applications:status", kwargs={"pk": application.pk}
        )
    )
    dialog = logged_in_page.get_by_role("dialog")
    trigger = logged_in_page.get_by_role("button", name="Withdraw application")

    trigger.click()

    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("button", name="Keep application")).to_be_focused()

    # Tab from the last control wraps to the first instead of leaving the dialog.
    logged_in_page.keyboard.press("Tab")
    expect(dialog.get_by_role("button", name="Withdraw application")).to_be_focused()
    logged_in_page.keyboard.press("Tab")
    expect(dialog.get_by_role("button", name="Keep application")).to_be_focused()

    logged_in_page.keyboard.press("Escape")

    expect(dialog).to_be_hidden()
    expect(trigger).to_be_focused()

    trigger.click()
    dialog.get_by_role("button", name="Withdraw application").click()

    expect(
        logged_in_page.get_by_role("heading", name="You withdrew your application")
    ).to_be_visible()
