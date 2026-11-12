"""A phone question on the application form, in a real browser: the country
picker, the refusal that hands back the typed number and the chosen country,
and the page layout."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from freedom_ls.accounts.models import User
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
    live_server: LiveServer, logged_in_page: Page, logged_in_user: User
) -> None:
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
    expect(logged_in_page.get_by_text("For example:")).to_be_hidden()
    logged_in_page.get_by_label("Phone number").fill("82 123 4567")
    logged_in_page.get_by_role("button", name="Next").click()

    expect(
        logged_in_page.get_by_text("Choose a country, or start the number")
    ).to_be_visible()
    expect(logged_in_page.get_by_label("Phone number")).to_have_value("82 123 4567")
    for viewport in QA_VIEWPORTS:
        logged_in_page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(logged_in_page)

    logged_in_page.get_by_label("Country").select_option("ZA")
    logged_in_page.get_by_role("button", name="Next").click()

    expect(logged_in_page.get_by_label("Upload your ID")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.browser_context_args(locale="en-ZA")
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_an_applicant_whose_browser_names_a_country_finds_it_chosen(
    live_server: LiveServer, logged_in_page: Page, logged_in_user: User
) -> None:
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
    expect(country.locator("option:checked")).to_have_text("South Africa (+27)")
    expect(logged_in_page.get_by_text("For example: 71 123 4567")).to_be_visible()
    logged_in_page.get_by_label("Your name").fill("Ada Lovelace")
    logged_in_page.get_by_label("Phone number").fill("082 123 4567")
    logged_in_page.get_by_role("button", name="Next").click()

    expect(logged_in_page.get_by_text("Leave out the 0 at the start")).to_be_visible()

    logged_in_page.get_by_label("Phone number").fill("82 123 4567")
    logged_in_page.get_by_role("button", name="Next").click()
    logged_in_page.get_by_role("button", name="Next").click()

    expect(logged_in_page.get_by_text("+27 82 123 4567")).to_be_visible()

    logged_in_page.get_by_role("link", name="Edit About you").click()

    expect(
        logged_in_page.get_by_label("Country").locator("option:checked")
    ).to_have_text("South Africa (+27)")
    expect(logged_in_page.get_by_label("Phone number")).to_have_value("82 123 4567")
    for viewport in QA_VIEWPORTS:
        logged_in_page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(logged_in_page)


@pytest.mark.playwright
@pytest.mark.browser_context_args(locale="en-ZA")
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_the_example_hint_follows_the_chosen_country(
    live_server: LiveServer, logged_in_page: Page, logged_in_user: User
) -> None:
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

    hint = logged_in_page.get_by_text("For example:")
    expect(hint).to_have_text("For example: 71 123 4567")

    logged_in_page.get_by_label("Country").select_option("GB")

    expect(hint).to_have_text("For example: 7400 123456")

    logged_in_page.get_by_label("Country").select_option("")

    expect(hint).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.browser_context_args(locale="en-ZA")
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_the_example_hint_starts_on_the_country_the_picker_shows(
    live_server: LiveServer, logged_in_page: Page, logged_in_user: User
) -> None:
    course, form = gated_course_with_form()
    FormQuestionFactory(
        form_page=form.pages.get(order=0),
        type="phone",
        order=10,
        question="Your phone number",
        required=False,
    )
    # A browser restoring the form after a reload moves the picker before the
    # hint starts and fires no change event. Doing the same here, as the picker
    # is parsed, does not depend on which browsers restore a select.
    logged_in_page.add_init_script(
        """
        new MutationObserver(() => {
            const picker = document.querySelector('select[name^="phone_country_"]');
            if (picker && picker.querySelector('option[value="GB"]')) {
                picker.value = "GB";
            }
        }).observe(document, { childList: true, subtree: true });
        """
    )

    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )

    country = logged_in_page.get_by_label("Country")
    expect(country.locator("option:checked")).to_have_text("United Kingdom (+44)")
    expect(logged_in_page.get_by_text("For example:")).to_have_text(
        "For example: 7400 123456"
    )
