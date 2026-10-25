"""E2E Playwright flow for the learner import: upload a file with errors,
filter the preview to the errors, confirm, read the result and download the
error file. The classification and wording are covered by the Client tests;
what only a browser shows is the file upload, the download and the layout of
the preview and result pages at every viewport.
"""

from __future__ import annotations

import re
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
    page.get_by_role("link", name="Import learners").click()
    page.get_by_label("File").set_input_files(str(upload))
    page.get_by_role("button", name="Upload and preview").click()

    expect(page.get_by_text("Step 2 of 3")).to_be_visible()
    page.get_by_role("link", name="Error: 1").click()
    expect(page).to_have_url(re.compile(r"label=error"))
    rows = page.locator("table tbody tr")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("not-an-email")

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
    page.set_viewport_size(QA_VIEWPORTS[-1])

    page.get_by_role("button", name="Add 2 learners").click()

    expect(page.get_by_text("Step 3 of 3")).to_be_visible()
    expect(page.get_by_text("Added 2 learners. 1 row was not added.")).to_be_visible()
    with page.expect_download() as download_info:
        page.get_by_role("link", name="Download the 1 error row").click()
    download = download_info.value
    content = Path(download.path()).read_text(encoding="utf-8-sig")
    assert content.splitlines()[0] == "email,first_name,last_name,cohort,reason"
    assert "not-an-email" in content

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
