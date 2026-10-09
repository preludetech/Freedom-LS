"""Browser flow for the instance page's dialogs and live heading.

The stub views have no authentication, so the flow needs no login.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from freedom_ls.tests.playwright_helpers import assert_no_horizontal_overflow

from ..helpers import make_stub
from ..stub_models import StubModel

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

    # A read-only fragment focuses its heading on open.
    page.get_by_role("button", name="View Info").click()
    expect(page.get_by_role("heading", name="Stub Info")).to_be_focused()

    # A click in the dialog's own padding leaves it open.
    modal.click(position={"x": 5, "y": 5})
    expect(modal).to_be_visible()

    # A backdrop click closes it. The viewport corner is clear of the centred
    # dialog, so the click lands on its ::backdrop.
    page.mouse.click(5, 5)
    expect(modal).to_be_hidden()

    # The instance heading updates when instanceTitleChanged fires.
    heading = page.locator("#instance-title")
    expect(heading).to_have_text("Original Name")
    page.evaluate(
        "document.dispatchEvent(new CustomEvent('instanceTitleChanged', "
        "{ detail: { title: 'Renamed' } }))"
    )
    expect(heading).to_have_text("Renamed")

    # A long title with no spaces does not widen the page.
    page.set_viewport_size(_NARROW_VIEWPORT)
    page.goto(f"{base}/{long_stub.pk}")
    expect(page.locator("#instance-title")).to_have_text(_LONG_UNBROKEN_NAME)
    assert_no_horizontal_overflow(page)
    assert page.evaluate("document.documentElement.scrollWidth") == 392

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
