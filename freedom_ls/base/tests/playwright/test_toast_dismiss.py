"""E2E tests for toast dismissal and stack ordering.

Covers two QA bugs surfaced in `qa_report.md`:

- Bug 1 — Clicking the close button must remove the toast root from the
  DOM (not just hide it). Previously `dismiss()` referenced `this.$el`,
  which Alpine binds to the close *button* when the handler fires from
  `x-on:click` on the button — leaving the toast root attached forever
  and silently breaking the stacking-cap accounting.
- Bug 2 — The newest toast must render at the bottom of the stack
  (closest to the viewport edge), per the spec's bottom-anchored
  conventions. Previously the regions used `flex flex-col-reverse`, so
  the most recently appended DOM child (the newest toast) rendered at
  the top of the column.

Both tests inject toast markup directly into the live ARIA regions —
this isolates the Alpine `toast` component's behaviour from any
particular server flow and matches the same approach used in the manual
QA pass.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


def _inject_toast(page: Page, region_id: str, toast_id: str, severity: str) -> None:
    """Append a minimal Alpine-bound toast to one of the ARIA regions.

    Alpine.js 3's mutation observer picks up the new ``x-data`` node and
    instantiates the `toast` component naturally, so timers and event
    handlers wire up the same as a server-rendered toast.
    """
    page.evaluate(
        """
        ({ regionId, toastId, severity }) => {
            const region = document.getElementById(regionId);
            const div = document.createElement('div');
            div.innerHTML = `
                <div id="${toastId}"
                     x-data="toast"
                     data-severity="${severity}"
                     aria-atomic="true"
                     x-show="show"
                     class="pointer-events-auto bg-surface rounded-lg p-4 w-96">
                    <p>Test ${toastId}</p>
                    <button x-on:click="dismiss"
                            type="button"
                            aria-label="Dismiss notification">X</button>
                </div>`.trim();
            region.appendChild(div.firstElementChild);
        }
        """,
        {"regionId": region_id, "toastId": toast_id, "severity": severity},
    )


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_close_button_removes_toast_from_dom(logged_in_page: Page) -> None:
    """Clicking the close button removes the toast element from the DOM.

    Regression for QA Bug 1: previously the toast root remained attached
    after the close-button click (only the button itself was removed),
    which broke `_enforceCap`'s child-count accounting and leaked
    window blur/focus listeners.
    """
    page = logged_in_page

    # Inject an error toast so it's persistent — no auto-dismiss timer
    # racing with the click.
    _inject_toast(
        page,
        region_id="toast-region-assertive",
        toast_id="toast-bug1",
        severity="error",
    )

    toast = page.locator("#toast-bug1")
    expect(toast).to_be_visible()

    toast.get_by_role("button", name="Dismiss notification").click()

    # `dismiss()` waits for the leave transition (~150ms) before removing
    # the element via setTimeout(..., 200). Playwright's auto-waiting
    # `to_have_count(0)` covers the timing.
    expect(toast).to_have_count(0)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_newest_toast_renders_at_bottom_of_stack(logged_in_page: Page) -> None:
    """The newest toast must sit closest to the viewport edge.

    Regression for QA Bug 2: per spec ("Stack behaviour — newest at the
    bottom, older toasts pushed up"), the most recently inserted toast
    should have the largest y-coordinate of the stack on a bottom-
    anchored layout.
    """
    page = logged_in_page

    # Three error toasts so they're all persistent and visible together.
    for i in (1, 2, 3):
        _inject_toast(
            page,
            region_id="toast-region-assertive",
            toast_id=f"toast-stack-{i}",
            severity="error",
        )

    expect(page.locator("#toast-stack-1")).to_be_visible()
    expect(page.locator("#toast-stack-2")).to_be_visible()
    expect(page.locator("#toast-stack-3")).to_be_visible()

    box1 = page.locator("#toast-stack-1").bounding_box()
    box2 = page.locator("#toast-stack-2").bounding_box()
    box3 = page.locator("#toast-stack-3").bounding_box()
    assert box1 is not None
    assert box2 is not None
    assert box3 is not None

    # Newest (#3) closest to viewport edge → largest y. Oldest (#1)
    # pushed furthest up → smallest y.
    assert box1["y"] < box2["y"] < box3["y"], (
        f"Expected newest toast at bottom of stack; "
        f"got y={box1['y']}, {box2['y']}, {box3['y']}"
    )
