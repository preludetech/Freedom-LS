"""The applicant's whole journey in a real browser.

The file question is the reason this test exists: attaching, seeing it survive a
navigation away and back, and removing it are all HTMX swaps that no pytest
client test can prove work.
"""

from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, expect

from django.core import mail
from django.utils import timezone

from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.form_engine.uploads import MAX_UPLOAD_BYTES
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.images import png_bytes
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.models import CourseApplication

from ..helpers import gated_course_with_form


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
    # The rows line up with their heading rather than sitting in the list's
    # default indent.
    heading_box = logged_in_page.get_by_role(
        "heading", name="Your applications"
    ).bounding_box()
    row_box = logged_in_page.get_by_role("listitem").first.bounding_box()
    assert heading_box is not None
    assert row_box is not None
    assert row_box["x"] == pytest.approx(heading_box["x"], abs=1)
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


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_an_anonymous_visitor_can_apply_from_details_to_submit(
    live_server, live_server_site, mock_site_context, page: Page, tmp_path
):
    course, _form = gated_course_with_form()
    scan = tmp_path / "id-scan.png"
    scan.write_bytes(png_bytes())

    page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )

    # No account yet: the first step asks who is applying.
    expect(page.get_by_role("heading", name="Your details")).to_be_visible()
    details_url = page.url
    page.get_by_label("Email").fill("anon.applicant@example.com")
    page.get_by_label("First name").fill("Ada")
    page.get_by_role("button", name="Next").click()

    notice = page.get_by_test_id("claim-link-notice")
    expect(notice).to_be_visible()
    expect(notice).to_contain_text("anon.applicant@example.com")

    # The dashboard lists the unfinished draft and resumes it on page 1.
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    expect(page.get_by_text("Incomplete")).to_be_visible()
    page.get_by_role("link", name="Continue application").click()
    expect(page.get_by_label("Your name")).to_be_visible()

    page.get_by_label("Your name").fill("Ada Lovelace")
    form_page_url = page.url
    page.get_by_role("button", name="Next").click()

    page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(page.get_by_text("id-scan.png")).to_be_visible()

    page.get_by_role("button", name="Remove").click()
    expect(page.get_by_text("id-scan.png")).to_be_hidden()

    page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(page.get_by_text("id-scan.png")).to_be_visible()
    page.get_by_role("button", name="Next").click()

    # Before the submit: once it is in, the session can no longer open the
    # form pages, only the status page.
    check_url = page.url
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(details_url)
        assert_no_horizontal_overflow(page)
        page.goto(form_page_url)
        assert_no_horizontal_overflow(page)
    page.goto(check_url)

    page.get_by_role("button", name="Submit application").click()
    expect(page.get_by_text("Before anyone reviews it")).to_be_visible()
    expect(page.get_by_test_id("claim-link-notice")).to_be_visible()
    page.get_by_role("button", name="Change email address").click()
    expect(page.get_by_test_id("change-email-form")).to_be_visible()

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_claim_link_from_the_details_step_signs_a_second_browser_in_on_the_draft(
    live_server, live_server_site, mock_site_context, page: Page, browser
):
    """The live server shares the test process, so the locmem outbox holds the
    email the details step sent."""
    course, _form = gated_course_with_form()
    page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )
    page.get_by_label("Email").fill("anon.applicant@example.com")
    page.get_by_label("First name").fill("Ada")
    page.get_by_role("button", name="Next").click()
    expect(page.get_by_test_id("claim-link-notice")).to_be_visible()

    (claim_email,) = mail.outbox
    claim_url = re.search(r"https?://[^\s\"<>]*/claim/[^\s\"<>]+", claim_email.body)
    assert claim_url is not None

    other_context = browser.new_context()
    try:
        other_page = other_context.new_page()
        other_page.goto(live_server.url + urlparse(claim_url.group(0)).path)
        expect(
            other_page.get_by_role(
                "heading", name=f"Continue your application for {course.title}"
            )
        ).to_be_visible()
        other_page.get_by_role("button", name="Confirm").click()

        other_page.get_by_label(re.compile(r"^Password:?$")).fill("a-Strong-pass-123")
        other_page.get_by_label(re.compile(r"^Password \(again\):?$")).fill(
            "a-Strong-pass-123"
        )
        other_page.get_by_role("button", name="Set Password").click()

        expect(other_page.get_by_label("Your name")).to_be_visible()
        other_page.goto(reverse_url(live_server, "learner_interface:dashboard"))
        expect(other_page.get_by_text("Incomplete")).to_be_visible()
        expect(other_page.get_by_role("link", name="Sign in")).to_be_hidden()
    finally:
        other_context.close()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_changing_the_address_from_the_notice_stays_on_the_form_page(
    live_server, live_server_site, mock_site_context, page: Page
):
    course, _form = gated_course_with_form()
    page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )
    page.get_by_label("Email").fill("anon.applicant@example.com")
    page.get_by_label("First name").fill("Ada")
    page.get_by_role("button", name="Next").click()
    notice = page.get_by_test_id("claim-link-notice")
    expect(notice).to_be_visible()
    form_page_url = page.url
    mail.outbox.clear()

    change_form = page.get_by_test_id("change-email-form")
    expect(change_form).to_be_hidden()
    notice.get_by_role("button", name="Change email address").click()
    expect(change_form).to_be_visible()
    page.get_by_label("New email address").fill("ada.lovelace@example.com")
    change_form.get_by_role("button", name="Update").click()

    expect(notice).to_contain_text("ada.lovelace@example.com")
    expect(change_form).to_be_hidden()
    assert page.url == form_page_url
    assert [message.to for message in mail.outbox] == [["ada.lovelace@example.com"]]


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_send_again_from_the_notice_says_a_new_link_went(
    live_server, live_server_site, mock_site_context, page: Page
):
    course, _form = gated_course_with_form()
    page.goto(
        reverse_url(
            live_server,
            "course_applications:apply",
            kwargs={"course_slug": course.slug},
        )
    )
    page.get_by_label("Email").fill("anon.applicant@example.com")
    page.get_by_label("First name").fill("Ada")
    page.get_by_role("button", name="Next").click()
    notice = page.get_by_test_id("claim-link-notice")
    expect(notice).to_be_visible()
    form_page_url = page.url
    mail.outbox.clear()

    notice.get_by_role("button", name="Send again").click()

    expect(notice).to_contain_text(
        "We've sent a new link to anon.applicant@example.com"
    )
    expect(notice.get_by_role("button", name="Send again")).to_have_count(0)
    assert page.url == form_page_url
    assert len(mail.outbox) == 1


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_learner_pages_through_their_applications(
    live_server, logged_in_page: Page, logged_in_user, mock_site_context
):
    page = logged_in_page
    applications = []
    now = timezone.now()
    for index in range(4):
        course = CourseFactory(
            title=f"Gated Course {index + 1}",
            slug=f"gated-course-{index + 1}",
            access_config={"access_type": "application_gated"},
        )
        application = CourseApplicationFactory(user=logged_in_user, course=course)
        CourseApplication.objects.filter(pk=application.pk).update(
            created_at=now - timedelta(days=4 - index)
        )
        applications.append(application)
    for letter in "ABCD":
        CourseFactory(
            title=f"Free Course {letter}",
            slug=f"free-course-{letter.lower()}",
            access_config={"access_type": "free"},
        )
    dashboard_url = reverse_url(live_server, "learner_interface:dashboard")
    panel = page.locator("#applications-page")

    page.goto(dashboard_url)
    expect(panel.get_by_role("link", name="Gated Course 4", exact=True)).to_be_visible()
    expect(panel.get_by_role("link", name="Gated Course 1", exact=True)).to_have_count(
        0
    )

    panel.get_by_role("link", name="Next page").click()

    expect(panel.get_by_role("link", name="Gated Course 1", exact=True)).to_be_visible()
    expect(panel.get_by_role("link", name="Gated Course 4", exact=True)).to_have_count(
        0
    )
    expect(page.get_by_role("heading", name="Your applications")).to_be_visible()
    expect(page).to_have_url(dashboard_url)
    expect(page.locator("#applications-status")).to_have_text(
        "Your applications: showing 4 to 4 of 4"
    )

    # Paging a course section leaves the applications page where it was.
    available = page.locator("#section-page-available")
    available.get_by_role("link", name="Next page").click()
    expect(panel.get_by_role("link", name="Gated Course 1", exact=True)).to_be_visible()
    expect(panel.get_by_role("link", name="Gated Course 4", exact=True)).to_have_count(
        0
    )

    # Below sm the row's button gives way to a chevron.
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(dashboard_url)
    rows = panel.get_by_role("listitem")
    expect(panel.get_by_role("link", name="Continue application")).to_be_hidden()
    expect(panel.get_by_role("link", name="View my application")).to_be_hidden()
    for index in range(rows.count()):
        expect(
            rows.nth(index)
            .locator('span.sm\\:hidden[aria-hidden="true"]')
            .locator("svg")
        ).to_be_visible()

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(dashboard_url)
        assert_no_horizontal_overflow(page)
