"""E2E tests for toast dismissal and stack ordering.

Covers two toast defects:

- Clicking the close button must remove the toast root from the
  DOM (not just hide it). Previously `dismiss()` referenced `this.$el`,
  which Alpine binds to the close *button* when the handler fires from
  `x-on:click` on the button — leaving the toast root attached forever
  and silently breaking the stacking-cap accounting.
- The newest toast must render at the bottom of the stack
  (closest to the viewport edge) in the bottom-anchored
  layout. Previously the regions used `flex flex-col-reverse`, so
  the most recently appended DOM child (the newest toast) rendered at
  the top of the column.

The test injects toast markup directly into the live ARIA regions —
this isolates the Alpine `toast` component's behaviour from any
particular server flow and matches how a manual check would drive them.
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
def test_toast_dismissal_and_stack_order(logged_in_page: Page) -> None:
    """Dismissing a toast removes its root from the DOM, then new toasts stack newest-lowest.

    The toast root used to stay attached after the close-button click (only the
    button itself was removed), which broke `_enforceCap`'s child-count
    accounting and leaked window blur/focus listeners. The newest toast must
    sit closest to the viewport edge: older toasts are pushed up, so the most
    recently inserted toast has the largest y-coordinate of the stack.
    """
    page = logged_in_page

    # An error toast is persistent: no auto-dismiss timer races the click.
    _inject_toast(
        page,
        region_id="toast-region-assertive",
        toast_id="toast-dismissed",
        severity="error",
    )
    toast = page.locator("#toast-dismissed")
    expect(toast).to_be_visible()

    toast.get_by_role("button", name="Dismiss notification").click()

    # `dismiss()` waits for the leave transition (~150ms) before removing
    # the element via setTimeout(..., 200). Playwright's auto-waiting
    # `to_have_count(0)` covers the timing.
    expect(toast).to_have_count(0)

    for i in (1, 2, 3):
        _inject_toast(
            page,
            region_id="toast-region-assertive",
            toast_id=f"toast-stack-{i}",
            severity="error",
        )
    for i in (1, 2, 3):
        expect(page.locator(f"#toast-stack-{i}")).to_be_visible()

    boxes = [page.locator(f"#toast-stack-{i}").bounding_box() for i in (1, 2, 3)]
    ys = []
    for box in boxes:
        assert box is not None
        ys.append(box["y"])
    assert ys[0] < ys[1] < ys[2], (
        f"Expected newest toast at bottom of stack; got y={ys}"
    )
