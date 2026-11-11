"""A phone question on the application form, in a real browser: the country
picker, the refusal that hands back the typed number and the chosen country,
and the page layout."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.conftest import reverse_url
from freedom_ls.form_engine.factories import FormQuestionFactory
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from ..helpers import gated_course_with_form


@pytest.mark.playwright
@pytest.mark.browser_context_args(locale="en")
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_an_applicant_is_asked_for_a_country_before_a_national_number_is_accepted(
    live_server, logged_in_page: Page, logged_in_user
):
    course, form = gated_course_with_form()
    FormQuestionFactory(
        form_page=form.pages.get(order=0),
        type="phone",
        order=10,
        question="Your phone number",
        required=False,
    )

    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )

    country = logged_in_page.get_by_label("Country")
    expect(country.locator("option:checked")).to_have_text("Choose a country")
    logged_in_page.get_by_label("Your name").fill("Ada Lovelace")
    logged_in_page.get_by_label("Phone number").fill("082 123 4567")
    logged_in_page.get_by_role("button", name="Next").click()

    expect(
        logged_in_page.get_by_text("Choose a country, or start the number")
    ).to_be_visible()
    expect(logged_in_page.get_by_label("Phone number")).to_have_value("082 123 4567")
    for viewport in QA_VIEWPORTS:
        logged_in_page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(logged_in_page)

    logged_in_page.get_by_label("Country").select_option("ZA")
    logged_in_page.get_by_role("button", name="Next").click()

    expect(logged_in_page.get_by_label("Upload your ID")).to_be_visible()
