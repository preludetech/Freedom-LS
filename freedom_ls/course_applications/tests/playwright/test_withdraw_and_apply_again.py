"""Withdrawing an application through the confirm dialog, in a real browser.

Focus handling, the Tab trap and Escape are browser behaviour that no pytest
client test can prove.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.tests.helpers import gated_course_with_form
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_withdraw_and_apply_again_flow(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
) -> None:
    """Withdrawing through the confirm dialog, then applying again.

    Proves: the dialog focuses Keep application, Tab wraps inside it, Escape
    closes it and returns focus to the trigger, Withdraw shows the withdrawn
    heading, Apply again lands on page 1 of a new application, and there is no
    horizontal overflow at the QA viewports.
    """
    course, _form = gated_course_with_form()
    application = CourseApplicationFactory(user=logged_in_user, course=course)
    logged_in_page.goto(
        reverse_url(
            live_server, "course_applications:status", kwargs={"pk": application.pk}
        )
    )
    dialog = logged_in_page.get_by_role("dialog")
    trigger = logged_in_page.get_by_role("button", name="Withdraw application")

    trigger.click()

    expect(dialog, "confirm dialog opens").to_be_visible()
    expect(
        dialog.get_by_role("button", name="Keep application"),
        "Keep application focused on open",
    ).to_be_focused()

    # Tab from the last control wraps to the first instead of leaving the dialog.
    logged_in_page.keyboard.press("Tab")
    expect(
        dialog.get_by_role("button", name="Withdraw application"),
        "Tab moves to Withdraw",
    ).to_be_focused()
    logged_in_page.keyboard.press("Tab")
    expect(
        dialog.get_by_role("button", name="Keep application"),
        "Tab wraps to Keep application",
    ).to_be_focused()

    logged_in_page.keyboard.press("Escape")

    expect(dialog, "Escape closes the dialog").to_be_hidden()
    expect(trigger, "focus returns to the trigger").to_be_focused()

    trigger.click()
    dialog.get_by_role("button", name="Withdraw application").click()

    expect(
        logged_in_page.get_by_role("heading", name="You withdrew your application"),
        "withdrawn heading",
    ).to_be_visible()

    logged_in_page.get_by_role("link", name="Apply again").click()

    expect(logged_in_page, "Apply again lands on page 1").to_have_url(
        re.compile(r"/application/.+/page/1/")
    )
    for viewport in QA_VIEWPORTS:
        logged_in_page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(logged_in_page)
