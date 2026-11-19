"""Browser flow for the account area: the Personal details page and its sidebar.

The Django test client covers what the server renders. What only a browser
shows is covered here: the name and picture saving inline with their toasts,
the picture removed through its confirmation, the sidebar leading to allauth's
pages, and the layout at each viewport.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.accounts.models import User
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
PICTURE_LABEL = re.compile(r"^Profile picture")
NO_RELOAD_MARKER = "accountFlowMarker"


def assert_header_avatar(
    page: Page, *, name: str, initials: str, picture: bool
) -> None:
    """The header avatar shows the given state, and the page was not reloaded."""
    avatar = page.locator("#header-avatar")
    expect(avatar).to_contain_text(initials)
    expect(avatar.locator("img[data-profile-picture]")).to_have_count(
        1 if picture else 0
    )
    expect(
        page.get_by_role("button", name=f"Open user menu for {name}")
    ).to_be_visible()
    assert page.evaluate(f"window.{NO_RELOAD_MARKER}") is True


def test_change_the_name_inline_then_follow_the_sidebar(
    live_server, logged_in_page: Page, logged_in_user: User
) -> None:
    page = logged_in_page
    page.goto(reverse_url(live_server, "accounts:account_profile"))

    expect(page).to_have_url(
        reverse_url(
            live_server,
            "accounts:account_profile",
            kwargs={"path_string": "personal-details"},
        )
    )

    page.evaluate(f"window.{NO_RELOAD_MARKER} = true")
    page.get_by_label("First name").fill("Ada")
    page.get_by_label("Last name").fill("Lovelace")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.get_by_text("Name saved")).to_be_visible()
    expect(page.get_by_label("First name")).to_have_value("Ada")
    expect(page.get_by_label("Last name")).to_have_value("Lovelace")
    assert_header_avatar(page, name="Ada Lovelace", initials="AL", picture=False)
    stored = User._base_manager.get(pk=logged_in_user.pk)
    assert (stored.first_name, stored.last_name) == ("Ada", "Lovelace")

    page.get_by_label(PICTURE_LABEL).set_input_files(
        {"name": "me.jpg", "mimeType": "image/jpeg", "buffer": jpeg_bytes()}
    )
    page.get_by_role("button", name="Save picture").click()

    expect(page.get_by_text("Profile picture saved")).to_be_visible()
    preview = page.locator("main img[data-profile-picture]")
    expect(preview).to_have_attribute("src", PICTURE_SRC)
    saved_src = preview.get_attribute("src")
    assert_header_avatar(page, name="Ada Lovelace", initials="AL", picture=True)

    page.get_by_label(PICTURE_LABEL).set_input_files(
        {"name": "notes.png", "mimeType": "image/png", "buffer": b"just some text"}
    )
    page.get_by_role("button", name="Save picture").click()

    error = page.get_by_text(WRONG_TYPE)
    expect(error).to_be_visible()
    label = page.locator("label[for='id_profile_picture']")
    error_box = error.bounding_box()
    label_box = label.bounding_box()
    assert error_box is not None
    assert label_box is not None
    assert error_box["x"] == pytest.approx(label_box["x"], abs=1)
    expect(preview).to_have_attribute("src", saved_src)

    page.get_by_role("button", name="Remove picture").click()

    dialog = page.get_by_role("dialog", name="Remove your profile picture?")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("button", name="Remove", exact=True)).to_have_class(
        re.compile(r"\bbtn-error\b")
    )
    dialog.get_by_role("button", name="Remove", exact=True).click()

    expect(page.locator("#app-modal")).not_to_have_attribute("open", "")
    expect(page.get_by_text("Profile picture removed")).to_be_visible()
    expect(preview).to_have_count(0)
    expect(page.get_by_role("button", name="Remove picture")).to_have_count(0)
    assert_header_avatar(page, name="Ada Lovelace", initials="AL", picture=False)
    assert User._base_manager.get(pk=logged_in_user.pk).profile_picture.name == ""

    page.get_by_role("navigation", name="Account").get_by_role(
        "link", name="Email"
    ).click()

    expect(page).to_have_url(reverse_url(live_server, "account_email"))

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
