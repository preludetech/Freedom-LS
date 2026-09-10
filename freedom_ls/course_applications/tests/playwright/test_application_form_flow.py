"""The applicant's whole journey in a real browser.

The file question is the reason this test exists: attaching, seeing it survive a
navigation away and back, and removing it are all HTMX swaps that no pytest
client test can prove work.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.conftest import reverse_url
from freedom_ls.form_engine.uploads import MAX_UPLOAD_BYTES
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

    # Apply now is a link straight into the form: nothing to confirm yet.
    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )

    # Page 1: the required name question, then on to the documents page.
    logged_in_page.get_by_label("Your name").fill("Ada Lovelace")
    logged_in_page.get_by_role("button", name="Next").click()

    # Page 2: attach the file and see it named back.
    logged_in_page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(logged_in_page.get_by_text("id-scan.png")).to_be_visible()

    # Leave and come back: the file has to still be attached. The dashboard
    # says the application is unfinished, and the status page -- the "View my
    # application" CTA's destination -- routes a returning applicant back into
    # the form.
    logged_in_page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    expect(logged_in_page.get_by_text("Incomplete")).to_be_visible()
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
    logged_in_page.get_by_role("button", name="Next").click()

    # Edit the first page from the check page, and land straight back on it
    # with the new value showing.
    logged_in_page.get_by_role("link", name="Edit About you").click()
    logged_in_page.get_by_label("Your name").fill("Grace Hopper")
    logged_in_page.get_by_role("button", name="Save and return to your answers").click()
    expect(logged_in_page.get_by_text("Grace Hopper")).to_be_visible()

    # Submitting lands on the dashboard, where the application now waits on
    # a reviewer rather than on the applicant.
    logged_in_page.get_by_role("button", name="Submit application").click()
    expect(logged_in_page).to_have_url(
        reverse_url(live_server, "learner_interface:dashboard")
    )
    expect(logged_in_page.get_by_text("has been submitted")).to_be_visible()
    expect(logged_in_page.get_by_text("Pending review", exact=True)).to_be_visible()
    expect(logged_in_page.get_by_text("Incomplete")).to_be_hidden()

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


def _upload_requests(page: Page) -> list[str]:
    """Every file-upload request the page issues from now on, by URL."""
    seen: list[str] = []

    def record(request) -> None:
        if "/file/upload/" in request.url:
            seen.append(request.url)

    page.on("request", record)
    return seen


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_an_oversize_file_is_refused_in_the_browser_without_being_uploaded(
    live_server, logged_in_page: Page, logged_in_user, tmp_path
):
    """The size guard exists to spare the applicant the upload, so the proof is
    that no upload request leaves the browser at all."""
    course, _form = gated_course_with_form()
    too_big = tmp_path / "too-big.png"
    too_big.write_bytes(png_bytes() + b"\x00" * MAX_UPLOAD_BYTES)
    uploads = _upload_requests(logged_in_page)

    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )
    logged_in_page.get_by_label("Your name").fill("Ada Lovelace")
    logged_in_page.get_by_role("button", name="Next").click()

    logged_in_page.get_by_label("Upload your ID").set_input_files(str(too_big))

    # htmx issues the request from the change event itself, so by now it has
    # either gone or been refused.
    assert uploads == []
    expect(logged_in_page.get_by_text("Choose a smaller one")).to_be_visible()
    expect(logged_in_page.get_by_label("Upload your ID")).to_have_value("")
