"""The applicant's whole journey in a real browser.

The file question is the reason this test exists: attaching, seeing it survive a
navigation away and back, and removing it are all HTMX swaps that no pytest
client test can prove work.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.conftest import reverse_url
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.images import png_bytes

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from ..conftest import gated_course_with_form


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_an_applicant_can_fill_in_attach_change_and_submit(
    live_server, logged_in_page: Page, logged_in_user, tmp_path
):
    course, _form = gated_course_with_form()
    scan = tmp_path / "id-scan.png"
    scan.write_bytes(png_bytes())

    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )
    logged_in_page.get_by_role("button", name="Submit application").click()

    # Page 1: the required name question, then on to the documents page.
    logged_in_page.get_by_label("Your name").fill("Ada Lovelace")
    logged_in_page.get_by_role("button", name="Next").click()

    # Page 2: attach the file and see it named back.
    logged_in_page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(logged_in_page.get_by_text("id-scan.png")).to_be_visible()

    # Leave and come back: the file has to still be attached. The status page is
    # the "View my application" CTA's destination, and it routes a returning
    # applicant back into the form.
    logged_in_page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:status",
            kwargs={"pk": course.applications.get().pk},
        )
    )
    expect(logged_in_page.get_by_text("id-scan.png")).to_be_visible()

    # Removing it leaves the empty picker behind.
    logged_in_page.get_by_role("button", name="Remove").click()
    expect(logged_in_page.get_by_text("id-scan.png")).to_be_hidden()

    logged_in_page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(logged_in_page.get_by_text("id-scan.png")).to_be_visible()
    logged_in_page.get_by_role("button", name="Check your answers").click()

    # Change the name from the check page, and see the new value come back.
    logged_in_page.get_by_role("link", name="Change answer to Your name").click()
    logged_in_page.get_by_label("Your name").fill("Grace Hopper")
    logged_in_page.get_by_role("button", name="Next").click()
    logged_in_page.get_by_role("button", name="Check your answers").click()
    expect(logged_in_page.get_by_text("Grace Hopper")).to_be_visible()

    logged_in_page.get_by_role("button", name="Submit application").click()
    expect(logged_in_page.get_by_text("pending review")).to_be_visible()

    # A submitted application offers no way back into the answers.
    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:check_answers",
            kwargs={"pk": course.applications.get().pk},
        )
    )
    expect(
        logged_in_page.get_by_role("button", name="Submit application")
    ).to_be_hidden()
