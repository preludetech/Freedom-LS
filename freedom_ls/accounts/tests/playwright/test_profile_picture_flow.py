"""Browser flow for the account area: the Personal details page and its sidebar.

The Django test client covers what the server renders. What only a browser
shows is covered here: the name and picture saving inline with their toasts,
the picture removed through its confirmation, the sidebar leading to allauth's
pages, and the layout at each viewport.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Browser, Page, expect

from freedom_ls.accounts.models import User
from freedom_ls.accounts.tests.profile_picture_samples import jpeg_bytes
from freedom_ls.accounts.validators import WRONG_TYPE
from freedom_ls.conftest import reverse_url
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
    assert_no_space_below_field_row,
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


def test_the_name_and_picture_forms_save_with_javascript_off(
    live_server, browser: Browser, logged_in_page: Page, logged_in_user: User
) -> None:
    # Tall enough that the footer buttons sit above the bottom-right toast,
    # which nothing dismisses with JavaScript off.
    context = browser.new_context(
        java_script_enabled=False,
        storage_state=logged_in_page.context.storage_state(),
        viewport={"width": 1280, "height": 1400},
    )
    page = context.new_page()
    personal_details = reverse_url(
        live_server,
        "accounts:account_profile",
        kwargs={"path_string": "personal-details"},
    )
    page.goto(personal_details)

    page.get_by_label("First name").fill("Grace")
    page.get_by_label("Last name").fill("Hopper")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page).to_have_url(personal_details)
    expect(page.get_by_text("Name saved")).to_be_visible()
    expect(page.get_by_label("First name")).to_have_value("Grace")

    page.get_by_label(PICTURE_LABEL).set_input_files(
        {"name": "me.jpg", "mimeType": "image/jpeg", "buffer": jpeg_bytes()}
    )
    page.get_by_role("button", name="Save picture").click()

    expect(page).to_have_url(personal_details)
    expect(page.get_by_text("Profile picture saved")).to_be_visible()
    expect(page.locator("main img[data-profile-picture]")).to_have_attribute(
        "src", PICTURE_SRC
    )
    stored = User._base_manager.get(pk=logged_in_user.pk)
    assert stored.first_name == "Grace"
    context.close()


def test_personal_details_flow(
    live_server, logged_in_page: Page, logged_in_user: User
) -> None:
    """The Personal details page end to end.

    Proves: a name save leaves a chosen-but-unsaved picture in the file input
    and shows its initials; the account URL lands on Personal details; the
    forms' fields sit flush; name and picture save inline with toasts and
    without a reload, updating the header avatar; a wrong file type shows its
    error beside the label and keeps the saved picture; the remove dialog
    deletes the picture and keeps focus in the panel; submits sit in the card
    footers; an email address adds and removes; a wrong current password shows
    an alert; and the layout holds at each viewport.
    """
    page = logged_in_page
    page.goto(
        reverse_url(
            live_server,
            "accounts:account_profile",
            kwargs={"path_string": "personal-details"},
        )
    )
    page.get_by_label(PICTURE_LABEL).set_input_files(
        {"name": "me.jpg", "mimeType": "image/jpeg", "buffer": jpeg_bytes()}
    )
    page.get_by_label("First name").fill("Grace")
    page.get_by_label("Last name").fill("Hopper")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.get_by_text("Name saved")).to_be_visible()
    expect(page.locator("#account-picture-preview")).to_contain_text("GH")
    assert (
        page.get_by_label(PICTURE_LABEL).evaluate("input => input.files.length") == 1
    ), "name save dropped the chosen picture from the file input"

    # A fresh load, so the next steps start without the earlier toast or file.
    page.goto(reverse_url(live_server, "accounts:account_profile"))

    expect(page).to_have_url(
        reverse_url(
            live_server,
            "accounts:account_profile",
            kwargs={"path_string": "personal-details"},
        )
    )

    assert_no_space_below_field_row(page.locator("#account-name-form"))
    assert_no_space_below_field_row(page.locator("#account-picture-form"))
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
    # The refresh removed the button the closing dialog had refocused; focus
    # must land somewhere in the panel, not fall back to <body>.
    expect(
        page.locator('[data-panel="profile-picture"]:focus-within'),
        "focus fell out of the profile picture panel after the refresh",
    ).to_have_count(1)
    assert_header_avatar(page, name="Ada Lovelace", initials="AL", picture=False)
    assert User._base_manager.get(pk=logged_in_user.pk).profile_picture.name == ""

    for panel in ("name", "profile-picture", "password"):
        assert_submit_in_card_footer(page, panel)

    emails = page.locator('[data-panel="email-addresses"]')
    emails.get_by_role("button", name="Add email").click()
    dialog = page.get_by_role("dialog", name="Add an email address")
    dialog.get_by_label("Email").fill("second@example.com")
    dialog.get_by_role("button", name="Add email").click()

    row = emails.locator('[data-testid="email-address-row"]').filter(
        has_text="second@example.com"
    )
    expect(row).to_contain_text("Unverified")
    expect(emails.locator('input[type="radio"]')).to_have_count(0)
    row_box = row.bounding_box()
    remove = row.get_by_role("button", name="Remove second@example.com")
    remove_box = remove.bounding_box()
    assert row_box is not None
    assert remove_box is not None
    # The row's own actions sit on the row's line, not under the list.
    assert row_box["y"] <= remove_box["y"] <= row_box["y"] + row_box["height"]

    remove.click()
    dialog = page.get_by_role("dialog", name="Remove second@example.com?")
    dialog.get_by_role("button", name="Remove", exact=True).click()
    expect(row).to_have_count(0)

    password = page.locator('[data-panel="password"]')
    password.get_by_label("Current password").fill("not-the-password")
    password.get_by_label(re.compile(r"^New password:?$")).fill(
        "a-new-long-passphrase-2"
    )
    password.get_by_label("New password (again)").fill("a-new-long-passphrase-2")
    password.get_by_role("button", name="Change password").click()
    expect(password.get_by_role("alert")).to_be_visible()

    assert page.evaluate(f"window.{NO_RELOAD_MARKER} === true")

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
        if viewport["width"] < 1024:
            assert_toggle_in_heading_row(page)


def assert_submit_in_card_footer(page: Page, panel: str) -> None:
    """A panel form's submit sits in the card footer, under the fields."""
    section = page.locator(f'[data-panel="{panel}"]')
    submit = section.locator("footer button[type=submit]")
    expect(submit).to_have_count(1)
    form = section.locator("form")
    form_box = form.first.bounding_box()
    submit_box = submit.bounding_box()
    assert form_box is not None
    assert submit_box is not None
    assert submit_box["y"] >= form_box["y"] + form_box["height"]


def assert_toggle_in_heading_row(page: Page) -> None:
    """The navigation toggle sits at the left of the page heading, centred
    on its line."""
    toggle = page.get_by_role("button", name="Open navigation panel")
    heading = page.locator("#interface-main h1").first
    toggle_box = toggle.bounding_box()
    heading_box = heading.bounding_box()
    assert toggle_box is not None
    assert heading_box is not None
    assert toggle_box["x"] + toggle_box["width"] <= heading_box["x"]
    toggle_middle = toggle_box["y"] + toggle_box["height"] / 2
    heading_middle = heading_box["y"] + heading_box["height"] / 2
    assert toggle_middle == pytest.approx(heading_middle, abs=6)
