"""Browser flow for the instance page's dialogs and live heading.

The stub views have no authentication, so the flow needs no login.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub
from ..stub_models import StubModel
from .helpers import assert_no_horizontal_overflow

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_LONG_UNBROKEN_NAME = "maximilianoalexandrovich.longname.qa@example-university.com"
_NARROW_VIEWPORT = {"width": 392, "height": 850}


def test_instance_dialogs_and_heading(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    stub = make_stub(name="Original Name")
    long_stub = make_stub(name=_LONG_UNBROKEN_NAME)
    base = f"{live_server.url}/test-panel/framework/stubs"
    modal = page.locator("#app-modal")

    page.goto(f"{base}/{stub.pk}/__tabs/details")

    # A message dialog focuses its Close button on open.
    page.get_by_role("button", name="View Info").click()
    expect(modal.locator("footer button[x-on\\:click=cancel]")).to_be_focused()

    # A click in the dialog's own padding leaves it open.
    modal.click(position={"x": 5, "y": 5})
    expect(modal).to_be_visible()

    # A backdrop click closes it. The viewport corner is clear of the centred
    # dialog, so the click lands on its ::backdrop.
    page.mouse.click(5, 5)
    expect(modal).to_be_hidden()

    # A confirm dialog with a typed reason closes from the footer Cancel with
    # no discard prompt.
    page.get_by_role("button", name="Retire Item").click()
    dialog = page.get_by_role("dialog", name="Retire Item")
    expect(dialog.get_by_role("button", name="Cancel")).to_be_focused()
    reason = dialog.get_by_label("Reason (optional):")
    reason.fill("Typed but not needed")

    # Esc asks to discard; "Keep editing" puts focus back in the field, and
    # every further Esc asks again instead of closing the dialog.
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog", name="Discard changes?")).to_be_visible()
    page.get_by_role("button", name="Keep editing").click()
    expect(reason).to_have_value("Typed but not needed")
    expect(reason).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog", name="Discard changes?")).to_be_visible()
    page.get_by_role("button", name="Keep editing").click()
    expect(reason).to_be_focused()

    dialog.get_by_role("button", name="Cancel").click()
    expect(modal).to_be_hidden()
    expect(page.get_by_role("dialog", name="Discard changes?")).to_be_hidden()

    # The instance heading updates when instanceTitleChanged fires.
    heading = page.locator("#instance-title")
    expect(heading).to_have_text("Original Name")
    page.evaluate(
        "document.dispatchEvent(new CustomEvent('instanceTitleChanged', "
        "{ detail: { title: 'Renamed' } }))"
    )
    expect(heading).to_have_text("Renamed")

    # The tab title opens with the instance name even when the heading's text
    # is not what the title starts with.
    page.evaluate("document.title = 'Stale name — Scope — Site'")
    page.evaluate(
        "document.dispatchEvent(new CustomEvent('instanceTitleChanged', "
        "{ detail: { title: 'Renamed again' } }))"
    )
    assert page.title() == "Renamed again — Scope — Site"

    # The header re-requests itself when a header refresh event reaches the
    # body, so a change made elsewhere shows without a reload.
    subtitle = page.locator("#instance-header").get_by_text("Subtitle of Original Name")
    expect(subtitle).to_be_visible()
    StubModel.objects.filter(pk=stub.pk).update(name="Changed Elsewhere")
    page.evaluate("document.body.dispatchEvent(new CustomEvent('itemChanged'))")
    expect(
        page.locator("#instance-header").get_by_text("Subtitle of Changed Elsewhere")
    ).to_be_visible()
    StubModel.objects.filter(pk=stub.pk).update(name="Original Name")

    # A long title with no spaces does not widen the page.
    page.set_viewport_size(_NARROW_VIEWPORT)
    page.goto(f"{base}/{long_stub.pk}")
    expect(page.locator("#instance-title")).to_have_text(_LONG_UNBROKEN_NAME)
    assert_no_horizontal_overflow(page)

    # The delete dialog focuses Cancel, and confirming deletes the row and
    # navigates to the list.
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{base}/{stub.pk}/__tabs/details")
    page.get_by_role("button", name="Delete", exact=True).click()
    expect(page.get_by_role("button", name="Cancel")).to_be_focused()
    # Scoped to the dialog: the trigger with the same name sits behind it,
    # outside #app-modal.
    modal.get_by_role("button", name="Delete", exact=True).click()
    expect(modal).to_be_hidden()
    expect(page).to_have_url(f"{base}")
    assert not StubModel.objects.filter(pk=stub.pk).exists()


def test_refused_delete_moves_focus_to_its_error_notice(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """A delete refused on submit re-renders the dialog with an error notice,
    and focus must land on that notice. It used to fall back to the Cancel
    button, whose autofocus the swap re-applied after the refusal handler."""
    stub = make_stub(name="Refused")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/details")

    page.get_by_role("button", name="Delete Refused", exact=True).click()
    dialog = page.locator("#app-modal")
    expect(dialog.get_by_role("button", name="Cancel")).to_be_focused()

    dialog.get_by_role("button", name="Delete Refused", exact=True).click()
    notice = dialog.locator("[data-error-summary]")
    expect(notice).to_contain_text("It still has 1 learner.")
    expect(notice).to_be_focused()


@pytest.mark.parametrize(
    "viewport", [{"width": 1920, "height": 1080}, {"width": 375, "height": 812}]
)
def test_only_the_dialog_body_scrolls_between_full_width_header_and_footer(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
    viewport: dict[str, int],
) -> None:
    """The header and footer rules stopped short of the dialog's right edge
    because the dialog itself scrolled, so its scrollbar gutter sat beside
    them. Now the header and footer span the dialog's full width and, with tall content the body scrolls while the footer stays in view."""
    stub = make_stub(name="Scrolling")
    page.set_viewport_size(viewport)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/details")
    page.get_by_role("button", name="Retire Item").click()
    modal = page.locator("#app-modal")
    expect(modal.get_by_role("button", name="Cancel")).to_be_visible()
    # The phone sheet slides up; measure once it has settled.
    expect(modal).to_have_css("transform", "none")

    def measure() -> dict[str, float]:
        measured: dict[str, float] = modal.evaluate(
            """dialog => {
                const rect = (el) => el.getBoundingClientRect();
                const box = rect(dialog);
                const bw = parseFloat(getComputedStyle(dialog).borderLeftWidth);
                const header = rect(dialog.querySelector('#app-modal-body header'));
                const footer = rect(dialog.querySelector('#app-modal-body footer'));
                const body = dialog.querySelector('#app-modal-body [data-modal-scroll]');
                const style = getComputedStyle(body);
                return {
                    headerLeft: header.left - box.left - bw,
                    headerRight: box.right - bw - header.right,
                    footerLeft: footer.left - box.left - bw,
                    footerRight: box.right - bw - footer.right,
                    dialogScrolls: dialog.scrollHeight > dialog.clientHeight + 1,
                    bodyScrolls: body.scrollHeight > body.clientHeight + 1,
                    footerBottom: footer.bottom,
                    dialogBottom: box.bottom,
                    viewportHeight: innerHeight,
                };
            }"""
        )
        return measured

    short = measure()
    for key in ("headerLeft", "headerRight", "footerLeft", "footerRight"):
        assert abs(short[key]) <= 1, (key, short)

    modal.evaluate(
        """dialog => {
            const tall = document.createElement('div');
            tall.style.height = '3000px';
            dialog.querySelector('#app-modal-body [data-modal-scroll]').append(tall);
        }"""
    )
    tall = measure()
    assert tall["bodyScrolls"], tall
    assert not tall["dialogScrolls"], tall
    assert tall["footerBottom"] <= tall["viewportHeight"], tall
    for key in ("headerRight", "footerRight"):
        assert abs(tall[key]) <= 1, (key, tall)
    expect(modal.locator("#app-modal-body footer")).to_be_in_viewport()
    expect(modal.locator("#app-modal-body [data-modal-scroll]")).to_have_attribute(
        "data-more-below", "true"
    )


@pytest.mark.parametrize(
    "viewport", [{"width": 1920, "height": 1080}, {"width": 375, "height": 812}]
)
def test_dialog_body_content_has_equal_space_each_side_and_fade_only_when_needed(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
    viewport: dict[str, int],
) -> None:
    """The body's always-visible scrollbar track sat on top of its padding, so
    the content had less space on its left than on its right, and the bottom
    fade washed out the last lines even when everything fitted. The space from
    the dialog's edges to the content is now equal, the body keeps its bottom
    padding, and the fade shows only while content lies below the fold."""
    stub = make_stub(name="Equal space")
    page.set_viewport_size(viewport)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/details")
    page.get_by_role("button", name="Retire Item").click()
    modal = page.locator("#app-modal")
    expect(modal.get_by_role("button", name="Cancel")).to_be_visible()
    expect(modal).to_have_css("transform", "none")

    def measure() -> dict[str, float]:
        measured: dict[str, float] = modal.evaluate(
            """dialog => {
                const body = dialog.querySelector('#app-modal-body [data-modal-scroll]');
                const footer = dialog.querySelector('#app-modal-body footer');
                const box = dialog.getBoundingClientRect();
                const bw = parseFloat(getComputedStyle(dialog).borderLeftWidth);
                const kids = Array.from(body.children).filter(
                    (el) => el.getBoundingClientRect().width > 0);
                const first = kids[0].getBoundingClientRect();
                const last = kids[kids.length - 1].getBoundingClientRect();
                const fade = getComputedStyle(body, '::after');
                return {
                    left: first.left - box.left - bw,
                    right: box.right - bw - first.right,
                    track: body.offsetWidth - body.clientWidth,
                    gapAboveFooter: footer.getBoundingClientRect().top - last.bottom,
                    padTop: parseFloat(getComputedStyle(body).paddingTop),
                    fadeOpacity: parseFloat(fade.opacity),
                    scrolls: body.scrollHeight > body.clientHeight + 1,
                };
            }"""
        )
        return measured

    fits = measure()
    assert abs(fits["left"] - fits["right"]) <= 1, fits
    assert fits["gapAboveFooter"] >= fits["padTop"] - 1, fits
    assert not fits["scrolls"], fits
    assert fits["fadeOpacity"] == 0, fits

    body = modal.locator("#app-modal-body [data-modal-scroll]")
    modal.evaluate(
        """dialog => {
            const tall = document.createElement('div');
            tall.style.height = '3000px';
            dialog.querySelector('#app-modal-body [data-modal-scroll]').append(tall);
        }"""
    )
    expect(body).to_have_attribute("data-more-below", "true")
    page.wait_for_function(
        "getComputedStyle(document.querySelector('#app-modal-body [data-modal-scroll]'),"
        " '::after').opacity === '1'"
    )
    body.evaluate("el => { el.scrollTop = el.scrollHeight; }")
    expect(body).to_have_attribute("data-more-below", "false")
    page.wait_for_function(
        "getComputedStyle(document.querySelector('#app-modal-body [data-modal-scroll]'),"
        " '::after').opacity === '0'"
    )
    ended = measure()
    assert abs(ended["left"] - ended["right"]) <= 1, ended
