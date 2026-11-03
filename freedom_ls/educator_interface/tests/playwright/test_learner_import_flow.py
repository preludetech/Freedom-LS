"""E2E Playwright flow for the learner import: upload a file with errors,
filter the preview to the errors, confirm, read the result and download the
error file. The classification and wording are covered by the Client tests;
what only a browser shows is the file upload, the download and the layout of
the preview and result pages at every viewport.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_import_a_file_with_errors_then_download_the_error_rows(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
    tmp_path: Path,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    upload = tmp_path / "learners.csv"
    upload.write_text(
        "email,first_name,last_name,cohort\n"
        "ada@example.com,Ada,Lovelace,\n"
        "grace@example.com,Grace,Hopper,\n"
        "not-an-email,,,\n"
    )

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.get_by_role("link", name="Import learners").first.click()
    upload_url = page.url
    transfer = page.evaluate_handle(
        """([name, text]) => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([text], name, { type: "text/csv" }));
            return transfer;
        }""",
        ["learners.csv", upload.read_text()],
    )
    zone = page.get_by_text("Drop your CSV here")
    zone.dispatch_event("dragenter", {"dataTransfer": transfer})
    zone.dispatch_event("dragover", {"dataTransfer": transfer})
    expect(page.get_by_text("Drop to choose this file")).to_be_visible()
    zone.dispatch_event("drop", {"dataTransfer": transfer})
    expect(page.locator("[data-drop-zone]")).to_contain_text("learners.csv")

    picked = tmp_path / "picked.csv"
    picked.write_text(upload.read_text())
    page.get_by_label("CSV file").focus()
    page.get_by_label("CSV file").set_input_files(str(picked))
    expect(page.locator("[data-drop-zone]")).to_contain_text("picked.csv")
    page.get_by_role("button", name="Upload and preview").click()

    expect(page.get_by_text("Step 2 of 3")).to_be_visible()
    # The base list style puts a marker in the gap between inline items.
    for selector in (
        "nav[aria-label='Import steps'] li",
        "li:has(> a[data-label-filter])",
    ):
        markers = page.locator(selector).evaluate_all(
            "items => items.map(item => getComputedStyle(item).listStyleType)"
        )
        assert markers
        assert set(markers) == {"none"}
    page.get_by_role("link", name="Error: 1").click()
    expect(page).to_have_url(re.compile(r"label=error"))
    rows = page.locator("[data-import-rows] tbody tr")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("not-an-email")

    page.get_by_role("button", name="Add 2 learners").click()

    expect(page.get_by_text("Step 3 of 3")).to_be_visible()
    expect(page.get_by_text("Added 2 learners. 1 row was not added.")).to_be_visible()
    with page.expect_download() as download_info:
        page.get_by_role("link", name="Download the 1 error row").click()
    download = download_info.value
    content = Path(download.path()).read_text(encoding="utf-8-sig")
    assert content.splitlines()[0] == "email,first_name,last_name,cohort,reason"
    assert "not-an-email" in content

    result_url = page.url

    bad = tmp_path / "bad-header.csv"
    bad.write_text("name\nAda\n")

    def show_upload_error() -> None:
        page.goto(upload_url)
        page.get_by_label("CSV file").set_input_files(str(bad))
        page.get_by_role("button", name="Upload and preview").click()
        expect(page.locator("#main-content [role=alert]")).to_contain_text(
            "The file could not be uploaded."
        )

    # A confirmed import's preview URL shows the result, so the preview is
    # revisited through a fresh upload that is never confirmed.
    page.goto(upload_url)
    page.get_by_label("CSV file").set_input_files(str(upload))
    page.get_by_role("button", name="Upload and preview").click()
    expect(page.get_by_text("Step 2 of 3")).to_be_visible()
    preview_url = page.url

    visits: list[tuple[Callable[[], object], bool]] = [
        (lambda: page.goto(upload_url), False),
        (show_upload_error, False),
        (lambda: page.goto(preview_url + "?label=error"), True),
        (lambda: page.goto(result_url), False),
    ]
    for visit, is_preview in visits:
        for viewport in QA_VIEWPORTS:
            page.set_viewport_size(viewport)
            visit()
            assert_no_horizontal_overflow(page)
            if is_preview and viewport["width"] == 375:
                expect(page.get_by_text("Step 2 of 3: Preview")).to_be_visible()
                # The labels are visually hidden (sr-only), so they stay
                # "visible" to Playwright; their box collapses to a pixel.
                label_box = page.locator("[data-step-label]").first.bounding_box()
                assert label_box is not None
                assert label_box["width"] <= 1
