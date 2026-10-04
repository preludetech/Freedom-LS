"""E2E Playwright tests for #app-modal's position at desktop and phone widths.

Covers the open dialog's bounding box sitting centred in the viewport at
desktop width and pinned to the bottom edge at phone width, the close button staying inside the dialog's top-right
corner, and the form's button row fitting inside the dialog at phone width. Interaction behaviour lives in test_modal_form_htmx.py.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

_DESKTOP_VIEWPORT = {"width": 1024, "height": 800}
_PHONE_VIEWPORT = {"width": 375, "height": 812}


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_modal_is_centred_in_the_viewport_at_desktop_width(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.set_viewport_size(_DESKTOP_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()

    dialog = page.locator("#app-modal")
    expect(dialog).to_be_visible()
    box = dialog.bounding_box()
    assert box is not None
    left_gap = box["x"]
    right_gap = _DESKTOP_VIEWPORT["width"] - (box["x"] + box["width"])
    top_gap = box["y"]
    bottom_gap = _DESKTOP_VIEWPORT["height"] - (box["y"] + box["height"])
    assert left_gap == pytest.approx(right_gap, abs=2)
    assert top_gap == pytest.approx(bottom_gap, abs=2)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_modal_is_pinned_to_the_bottom_edge_at_phone_width(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.set_viewport_size(_PHONE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()

    dialog = page.locator("#app-modal")
    expect(dialog).to_be_visible()
    # The slide-up transition has to finish before the box is measured.
    page.wait_for_timeout(400)
    box = dialog.bounding_box()
    assert box is not None
    assert box["x"] == pytest.approx(0, abs=2)
    assert _PHONE_VIEWPORT["width"] - (box["x"] + box["width"]) == pytest.approx(
        0, abs=2
    )
    assert _PHONE_VIEWPORT["height"] - (box["y"] + box["height"]) == pytest.approx(
        0, abs=2
    )


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_close_button_stays_inside_the_dialog_top_right_corner(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.set_viewport_size(_DESKTOP_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()

    dialog = page.locator("#app-modal")
    close_button = page.get_by_role("button", name="Close")
    expect(dialog).to_be_visible()
    dialog_box = dialog.bounding_box()
    close_box = close_button.bounding_box()
    assert dialog_box is not None
    assert close_box is not None
    assert dialog_box["x"] <= close_box["x"] <= dialog_box["x"] + dialog_box["width"]
    assert dialog_box["y"] <= close_box["y"] <= dialog_box["y"] + dialog_box["height"]


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_form_buttons_fit_inside_the_dialog_at_phone_width(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.set_viewport_size(_PHONE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()

    dialog = page.locator("#app-modal")
    expect(dialog).to_be_visible()
    dialog_box = dialog.bounding_box()
    assert dialog_box is not None
    buttons = page.locator("#app-modal-body form button")
    expect(buttons.first).to_be_visible()
    heights: list[float] = []
    for button in buttons.all():
        box = button.bounding_box()
        assert box is not None
        assert box["x"] >= dialog_box["x"]
        assert box["x"] + box["width"] <= dialog_box["x"] + dialog_box["width"]
        heights.append(box["height"])
    # A label that word-wraps makes its button a whole line taller.
    assert max(heights) < 1.5 * min(heights)
