"""Browser flow for the account page: upload a picture, then a refused file.

The Django test client covers what the server renders. What only a browser
shows is covered here: choosing a file in the input, the saved picture beside
the name and in the header trigger, the refusal leaving that picture in place,
and the layout at each viewport.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.accounts.tests.profile_picture_samples import jpeg_bytes
from freedom_ls.accounts.validators import WRONG_TYPE
from freedom_ls.conftest import reverse_url
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

PICTURE_SRC = re.compile(r"profile_pictures/\d+/[0-9a-f]{32}\.webp")


def test_upload_a_picture_then_a_refused_file(
    live_server, logged_in_page: Page
) -> None:
    page = logged_in_page
    page.goto(reverse_url(live_server, "accounts:account_profile"))

    page.get_by_label("First name").fill("Ada")
    page.get_by_label("Last name").fill("Lovelace")
    page.get_by_label("Profile picture").set_input_files(
        {"name": "me.jpg", "mimeType": "image/jpeg", "buffer": jpeg_bytes()}
    )
    page.get_by_role("button", name="Save").click()

    expect(page.get_by_text("Profile saved")).to_be_visible()
    main = page.locator("main")
    expect(main.get_by_text("Ada Lovelace")).to_be_visible()
    expect(main.locator("img[data-profile-picture]")).to_have_attribute(
        "src", PICTURE_SRC
    )
    header = page.locator("header")
    expect(header.locator("img[data-profile-picture]")).to_have_attribute(
        "src", PICTURE_SRC
    )

    page.get_by_label("Profile picture").set_input_files(
        {"name": "notes.png", "mimeType": "image/png", "buffer": b"just some text"}
    )
    page.get_by_role("button", name="Save").click()

    expect(page.get_by_text(WRONG_TYPE)).to_be_visible()
    expect(main.locator("img[data-profile-picture]")).to_have_attribute(
        "src", PICTURE_SRC
    )
    expect(header.locator("img[data-profile-picture]")).to_have_attribute(
        "src", PICTURE_SRC
    )

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
