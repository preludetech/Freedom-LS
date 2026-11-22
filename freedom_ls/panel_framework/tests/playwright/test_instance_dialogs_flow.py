"""Browser flow for the instance page's dialogs and live heading.

The stub views have no authentication, so the flow needs no login.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Locator, Page, ViewportSize, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub
from ..stub_models import StubModel
from .helpers import assert_no_horizontal_overflow

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_LONG_UNBROKEN_NAME = "maximilianoalexandrovich.longname.qa@example-university.com"
_NARROW_VIEWPORT: ViewportSize = {"width": 392, "height": 850}
_LAYOUT_VIEWPORTS: tuple[ViewportSize, ...] = (
    {"width": 1920, "height": 1080},
    {"width": 375, "height": 812},
)


_BASE_PATH = "/test-panel/framework/stubs"


def _check_message_and_confirm_dialogs_and_live_heading(
    page: Page, base: str, stub: StubModel
) -> None:
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


def _check_refused_delete_moves_focus_to_its_error_notice(
    page: Page, base: str, stub: StubModel
) -> None:
    """A delete refused on submit re-renders the dialog with an error notice,
    and focus must land on that notice. It used to fall back to the Cancel
    button, whose autofocus the swap re-applied after the refusal handler."""
    page.goto(f"{base}/{stub.pk}/__tabs/details")

    page.get_by_role("button", name="Delete Refused", exact=True).click()
    dialog = page.locator("#app-modal")
    expect(dialog.get_by_role("button", name="Cancel")).to_be_focused()

    dialog.get_by_role("button", name="Delete Refused", exact=True).click()
    notice = dialog.locator("[data-error-summary]")
    expect(notice).to_contain_text("It still has 1 learner.")
    expect(notice).to_be_focused()


def _check_empty_required_reason_keeps_dialog_open(
    page: Page, base: str, stub: StubModel
) -> None:
    """A required reason is checked on the server only, since the field has no
    browser-side `required`. An empty submit must swap the 422 response into
    the open dialog with the error under the field and perform nothing; a
    typed reason then closes the dialog and runs the action."""
    page.goto(f"{base}/{stub.pk}/__tabs/details")

    page.get_by_role("button", name="Suspend Item").click()
    modal = page.locator("#app-modal")
    dialog = page.get_by_role("dialog", name="Suspend Item")
    reason = dialog.get_by_label("Reason")
    expect(reason).to_be_visible()

    dialog.get_by_role("button", name="Suspend Item").click()
    expect(modal).to_be_visible()
    expect(dialog.get_by_text("This field is required.")).to_be_visible()
    stub.refresh_from_db()
    assert stub.is_active

    reason.fill("No longer needed")
    dialog.get_by_role("button", name="Suspend Item").click()
    expect(modal).to_be_hidden()
    stub.refresh_from_db()
    assert not stub.is_active


def _check_long_title_does_not_widen_the_page(
    page: Page, base: str, long_stub: StubModel
) -> None:
    # A long title with no spaces does not widen the page.
    page.set_viewport_size(_NARROW_VIEWPORT)
    page.goto(f"{base}/{long_stub.pk}")
    expect(page.locator("#instance-title")).to_have_text(_LONG_UNBROKEN_NAME)
    assert_no_horizontal_overflow(page)


def _check_delete_dialog_removes_the_row(
    page: Page, base: str, stub: StubModel
) -> None:
    modal = page.locator("#app-modal")
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


def _check_retire_dialog_layout(
    page: Page, base: str, stub: StubModel, viewport: ViewportSize
) -> None:
    """The header and footer span the dialog's full width and, with tall
    content, only the body scrolls while the footer stays in view; the content
    has equal space each side and the fade shows only while content lies
    below the fold."""
    width = viewport["width"]
    page.set_viewport_size(viewport)
    page.goto(f"{base}/{stub.pk}/__tabs/details")
    page.get_by_role("button", name="Retire Item").click()
    modal = page.locator("#app-modal")
    expect(modal.get_by_role("button", name="Cancel")).to_be_visible()
    # The phone sheet slides up; measure once it has settled.
    expect(modal).to_have_css("transform", "none")

    short = _measure_edges(modal)
    for key in ("headerLeft", "headerRight", "footerLeft", "footerRight"):
        assert abs(short[key]) <= 1, (f"{key} gap at {width}px", short)

    fits = _measure_spacing(modal)
    assert abs(fits["left"] - fits["right"]) <= 1, (
        f"unequal side space at {width}px",
        fits,
    )
    assert fits["gapAboveFooter"] >= fits["padTop"] - 1, (
        f"gap above the footer smaller than the top padding at {width}px",
        fits,
    )
    assert not fits["scrolls"], (f"short content scrolls at {width}px", fits)
    assert fits["fadeOpacity"] == 0, (
        f"fade shown for short content at {width}px",
        fits,
    )

    modal.evaluate(
        """dialog => {
            const tall = document.createElement('div');
            tall.style.height = '3000px';
            dialog.querySelector('#app-modal-body [data-modal-scroll]').append(tall);
        }"""
    )
    tall = _measure_edges(modal)
    assert tall["bodyScrolls"], (f"body does not scroll at {width}px", tall)
    assert not tall["dialogScrolls"], (f"dialog scrolls at {width}px", tall)
    assert tall["footerBottom"] <= tall["viewportHeight"], (
        f"footer below the viewport at {width}px",
        tall,
    )
    for key in ("headerRight", "footerRight"):
        assert abs(tall[key]) <= 1, (f"{key} gap with tall content at {width}px", tall)
    expect(
        modal.locator("#app-modal-body footer"), f"footer out of view at {width}px"
    ).to_be_in_viewport()
    body = modal.locator("#app-modal-body [data-modal-scroll]")
    expect(body, f"more-below marker missing at {width}px").to_have_attribute(
        "data-more-below", "true"
    )
    page.wait_for_function(
        "getComputedStyle(document.querySelector('#app-modal-body [data-modal-scroll]'),"
        " '::after').opacity === '1'"
    )
    body.evaluate("el => { el.scrollTop = el.scrollHeight; }")
    expect(body, f"more-below marker kept at the end at {width}px").to_have_attribute(
        "data-more-below", "false"
    )
    page.wait_for_function(
        "getComputedStyle(document.querySelector('#app-modal-body [data-modal-scroll]'),"
        " '::after').opacity === '0'"
    )
    ended = _measure_spacing(modal)
    assert abs(ended["left"] - ended["right"]) <= 1, (
        f"unequal side space after scrolling at {width}px",
        ended,
    )


def _measure_edges(modal: Locator) -> dict[str, float]:
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


def _measure_spacing(modal: Locator) -> dict[str, float]:
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


def test_instance_dialogs_flow(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """One flow over the instance page's dialogs and live heading.

    Proves the message dialog's focus and backdrop; the confirm dialog's reason
    and discard prompt; the live heading, tab title and header refresh; that a
    refused delete focuses its error notice; that an empty required reason
    keeps the dialog open with an error until filled; that a long unbroken
    title does not widen the page; at 1920x1080 and 375x812 that the Retire
    Item dialog has a full-width header and footer, scrolls only its body and
    spaces its content equally with a fade only when needed; and that deleting
    removes the row and returns to the list.
    """
    base = f"{live_server.url}{_BASE_PATH}"
    stub = make_stub(name="Original Name")
    long_stub = make_stub(name=_LONG_UNBROKEN_NAME)
    refused_stub = make_stub(name="Refused")
    reason_stub = make_stub(name="Needs reason")
    layout_stub = make_stub(name="Layout")

    _check_message_and_confirm_dialogs_and_live_heading(page, base, stub)
    _check_refused_delete_moves_focus_to_its_error_notice(page, base, refused_stub)
    _check_empty_required_reason_keeps_dialog_open(page, base, reason_stub)
    _check_long_title_does_not_widen_the_page(page, base, long_stub)
    for viewport in _LAYOUT_VIEWPORTS:
        _check_retire_dialog_layout(page, base, layout_stub, viewport)
    _check_delete_dialog_removes_the_row(page, base, stub)
