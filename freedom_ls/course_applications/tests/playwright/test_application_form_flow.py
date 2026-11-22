"""The applicant's whole journey in a real browser.

The file question is the reason this test exists: attaching, seeing it survive a
navigation away and back, and removing it are all HTMX swaps that no pytest
client test can prove work.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser, Page, Request, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.sites.models import Site
from django.core import mail
from django.utils import timezone

from freedom_ls.accounts.models import User
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


def _upload_requests(page: Page) -> list[str]:
    """Every file-upload request the page issues from now on, by URL."""
    seen: list[str] = []

    def record(request: Request) -> None:
        if "/file/upload/" in request.url:
            seen.append(request.url)

    page.on("request", record)
    return seen


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_an_applicant_application_flow(
    live_server: LiveServer, logged_in_page: Page, logged_in_user: User, tmp_path: Path
) -> None:
    """A signed-in applicant fills in, attaches, changes their mind and submits.

    Proves: the employer page appears for Yes and takes an answer; an oversize
    file is refused in the browser without any upload request; answering No
    skips the employer page; a valid file attaches, survives leaving and
    returning, and can be removed and re-attached; the dashboard marks the
    draft unfinished with its rows aligned under the heading; a page can be
    edited from the check page; the review has no employer card after No;
    editing back to Yes brings the employer page and its earlier answer back;
    submitting lands on the dashboard waiting for review, and a submitted
    application offers no way back into the answers.
    """
    course, _form = gated_course_with_form(with_employer_case=True)
    scan = tmp_path / "id-scan.png"
    scan.write_bytes(png_bytes())
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
    logged_in_page.get_by_text("Yes", exact=True).click()
    logged_in_page.get_by_role("button", name="Next").click()
    logged_in_page.get_by_label("Employer name").fill("Analytical Engines Ltd")
    logged_in_page.get_by_role("button", name="Next").click()

    logged_in_page.get_by_label("Upload your ID").set_input_files(str(too_big))

    # htmx issues the request from the change event itself, so by now it has
    # either gone or been refused.
    assert uploads == [], "oversize file triggered an upload request"
    expect(
        logged_in_page.get_by_text("Choose a smaller one"),
        "oversize file error",
    ).to_be_visible()
    expect(
        logged_in_page.get_by_label("Upload your ID"),
        "oversize file left in the picker",
    ).to_have_value("")

    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:form_page",
            kwargs={"pk": course.applications.get().pk, "page_number": 1},
        )
    )
    logged_in_page.get_by_text("No", exact=True).click()
    logged_in_page.get_by_role("button", name="Next").click()

    expect(
        logged_in_page.get_by_text("Employer name"),
        "employer page skipped after No",
    ).to_be_hidden()
    logged_in_page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(
        logged_in_page.get_by_text("id-scan.png"), "attached file named back"
    ).to_be_visible()

    # Leave and come back: the file has to still be attached. The dashboard
    # says the application is unfinished, and the status page -- the "View my
    # application" CTA's destination -- offers a way back into the form.
    logged_in_page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    expect(
        logged_in_page.get_by_text("Not submitted"), "draft marked unfinished"
    ).to_be_visible()
    heading_box = logged_in_page.get_by_role(
        "heading", name="Your applications"
    ).bounding_box()
    row_box = logged_in_page.get_by_role("listitem").first.bounding_box()
    assert heading_box is not None, "applications heading has no box"
    assert row_box is not None, "first application row has no box"
    assert row_box["x"] == pytest.approx(heading_box["x"], abs=1), (
        "application rows indented from their heading"
    )
    logged_in_page.goto(
        reverse_url(
            live_server,
            "course_applications:status",
            kwargs={"pk": course.applications.get().pk},
        )
    )
    logged_in_page.get_by_role("link", name="Continue application").click()
    expect(
        logged_in_page.get_by_text("id-scan.png"), "file kept after leaving"
    ).to_be_visible()

    logged_in_page.get_by_role("button", name="Remove").click()
    expect(logged_in_page.get_by_text("id-scan.png"), "file removed").to_be_hidden()

    logged_in_page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(
        logged_in_page.get_by_text("id-scan.png"), "file attached again"
    ).to_be_visible()
    logged_in_page.get_by_role("button", name="Next").click()

    logged_in_page.get_by_role("link", name="Edit About you").click()
    logged_in_page.get_by_label("Your name").fill("Grace Hopper")
    logged_in_page.get_by_role("button", name="Save and return to your answers").click()
    expect(
        logged_in_page.get_by_text("Grace Hopper"), "edited name on the review"
    ).to_be_visible()
    expect(
        logged_in_page.get_by_role("link", name="Edit Your employer"),
        "employer card after No",
    ).to_have_count(0)

    # Editing the answer back to Yes brings the employer page back on the
    # path. Its required question already has the answer typed earlier, so the
    # applicant returns straight to a review that shows it.
    logged_in_page.get_by_role("link", name="Edit About you").click()
    logged_in_page.get_by_text("Yes", exact=True).click()
    logged_in_page.get_by_role("button", name="Save and return to your answers").click()

    expect(
        logged_in_page.get_by_role("link", name="Edit Your employer"),
        "employer card after Yes again",
    ).to_be_visible()
    expect(
        logged_in_page.get_by_text("Analytical Engines Ltd"),
        "earlier employer answer on the review",
    ).to_be_visible()
    logged_in_page.get_by_role("link", name="Edit Your employer").click()
    expect(
        logged_in_page.get_by_label("Employer name"), "employer answer restored"
    ).to_have_value("Analytical Engines Ltd")

    check_url = reverse_url(
        live_server,
        "course_applications:check_answers",
        kwargs={"pk": course.applications.get().pk},
    )
    logged_in_page.goto(check_url)
    logged_in_page.get_by_role("button", name="Submit application").click()
    expect(logged_in_page, "submit lands on the dashboard").to_have_url(
        reverse_url(live_server, "learner_interface:dashboard")
    )
    expect(
        logged_in_page.get_by_text("has been submitted"), "submitted message"
    ).to_be_visible()
    expect(
        logged_in_page.get_by_text("Waiting for review", exact=True),
        "waiting for review status",
    ).to_be_visible()
    expect(
        logged_in_page.get_by_text("Not submitted"), "unfinished marker after submit"
    ).to_be_hidden()

    logged_in_page.goto(check_url)
    expect(
        logged_in_page.get_by_role("button", name="Submit application"),
        "submit button on a submitted application",
    ).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_an_anonymous_applicant_flow(
    live_server: LiveServer,
    live_server_site: Site,
    mock_site_context: Site,
    page: Page,
    tmp_path: Path,
) -> None:
    """An anonymous visitor applies from the details step to the submit.

    Proves: the details step asks who is applying; the claim notice names the
    address; Send again says a new link went and sends one email; changing the
    address resends to the new address and stays on the form page; the
    dashboard lists the draft and its Details link resumes on page 1; a file
    attaches, removes and re-attaches; the pages have no horizontal overflow at
    the QA viewports; submitting keeps the notice and its change-email form.
    """
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

    expect(
        page.get_by_role("heading", name="Your details"), "details step heading"
    ).to_be_visible()
    details_url = page.url
    page.get_by_label("Email").fill("anon.applicant@example.com")
    page.get_by_label("First name").fill("Ada")
    page.get_by_role("button", name="Next").click()

    notice = page.get_by_test_id("claim-link-notice")
    expect(notice, "claim notice").to_be_visible()
    expect(notice, "claim notice address").to_contain_text("anon.applicant@example.com")
    notice_url = page.url
    mail.outbox.clear()

    notice.get_by_role("button", name="Send again").click()

    expect(notice, "send again confirmation").to_contain_text(
        "We've sent a new link to anon.applicant@example.com"
    )
    expect(
        notice.get_by_role("button", name="Send again"), "send again button after use"
    ).to_have_count(0)
    assert page.url == notice_url, "send again left the form page"
    assert len(mail.outbox) == 1, "send again did not send exactly one email"
    mail.outbox.clear()

    change_form = page.get_by_test_id("change-email-form")
    expect(change_form, "change-email form before opening").to_be_hidden()
    notice.get_by_role("button", name="Change email address").click()
    expect(change_form, "change-email form after opening").to_be_visible()
    page.get_by_label("New email address").fill("ada.lovelace@example.com")
    change_form.get_by_role("button", name="Update").click()

    expect(notice, "claim notice new address").to_contain_text(
        "ada.lovelace@example.com"
    )
    expect(change_form, "change-email form after update").to_be_hidden()
    assert page.url == notice_url, "changing the address left the form page"
    assert [message.to for message in mail.outbox] == [["ada.lovelace@example.com"]], (
        "changing the address did not resend to the new address"
    )

    # The dashboard lists the unfinished draft; an unclaimed draft's Details
    # link resumes it on page 1.
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    expect(page.get_by_text("Not submitted"), "draft marked unfinished").to_be_visible()
    page.locator("#applications-page").get_by_role("link", name="Details").click()
    expect(
        page.get_by_label("Your name"), "Details link resumes page 1"
    ).to_be_visible()

    page.get_by_label("Your name").fill("Ada Lovelace")
    form_page_url = page.url
    page.get_by_role("button", name="Next").click()

    page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(page.get_by_text("id-scan.png"), "file attached").to_be_visible()

    page.get_by_role("button", name="Remove").click()
    expect(page.get_by_text("id-scan.png"), "file removed").to_be_hidden()

    page.get_by_label("Upload your ID").set_input_files(str(scan))
    expect(page.get_by_text("id-scan.png"), "file attached again").to_be_visible()
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
    expect(
        page.get_by_text("Before anyone reviews it"), "status page after submit"
    ).to_be_visible()
    expect(
        page.get_by_test_id("claim-link-notice"), "claim notice after submit"
    ).to_be_visible()
    page.get_by_role("button", name="Change email address").click()
    expect(
        page.get_by_test_id("change-email-form"), "change-email form after submit"
    ).to_be_visible()

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_claim_link_from_the_details_step_signs_a_second_browser_in_on_the_draft(
    live_server: LiveServer,
    live_server_site: Site,
    mock_site_context: Site,
    page: Page,
    browser: Browser,
) -> None:
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

        other_page.get_by_role("link", name="Continue application").click()
        expect(other_page.get_by_label("Your name")).to_be_visible()
        other_page.goto(reverse_url(live_server, "learner_interface:dashboard"))
        expect(other_page.get_by_text("Not submitted")).to_be_visible()
        expect(other_page.get_by_role("link", name="Sign in")).to_be_hidden()
    finally:
        other_context.close()


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_a_rejected_rows_details_lead_to_apply_again_and_a_new_application(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
) -> None:
    course, _form = gated_course_with_form()
    rejected = CourseApplicationFactory(
        user=logged_in_user, course=course, rejected=True
    )
    dashboard_url = reverse_url(live_server, "learner_interface:dashboard")
    panel = logged_in_page.locator("#applications-page")

    logged_in_page.goto(dashboard_url)
    expect(panel.get_by_text("Declined", exact=True)).to_be_visible()
    expect(panel.get_by_role("link", name="Apply again")).to_have_count(0)
    panel.get_by_role("link", name="Details").click()
    logged_in_page.get_by_role("link", name="Apply again").click()

    expect(logged_in_page).to_have_url(re.compile(r"/application/.+/page/1/"))
    logged_in_page.goto(dashboard_url)
    expect(panel.get_by_text("Declined", exact=True)).to_have_count(0)
    expect(panel.get_by_text("Not submitted")).to_be_visible()
    assert CourseApplication.objects.filter(user=logged_in_user).count() == 2
    assert CourseApplication.objects.get(pk=rejected.pk).state == "rejected"


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_learner_pages_through_their_applications(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
) -> None:
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

    # On a phone each row still ends in its one Details link.
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(dashboard_url)
    rows = panel.get_by_role("listitem")
    expect(panel.get_by_role("link", name="Continue application")).to_have_count(0)
    expect(panel.get_by_role("link", name="View my application")).to_have_count(0)
    expect(panel.get_by_role("link", name="Details")).to_have_count(rows.count())
    expect(panel.get_by_role("link", name="Details").first).to_be_visible()

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(dashboard_url)
        assert_no_horizontal_overflow(page)
