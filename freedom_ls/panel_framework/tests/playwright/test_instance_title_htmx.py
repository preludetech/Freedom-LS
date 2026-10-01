"""The instance heading still updates live after an instanceTitleChanged event.

Panels re-fetch themselves on their own domain events through hx-trigger; the
page heading sits outside every panel, so alpine-components.js updates its
textContent by id instead. This proves panel-page-header still gives the
heading that id, once the plain <h1> is rendered through the component.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..conftest import _make_stub


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_instance_title_changed_event_updates_the_instance_heading(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="Original Name")
    instance_url = f"{live_server.url}/test-panel/framework/stubs/{stub.pk}"
    page.goto(instance_url)
    heading = page.locator("#instance-title")
    expect(heading).to_have_text("Original Name")

    page.evaluate(
        "document.dispatchEvent(new CustomEvent('instanceTitleChanged', "
        "{ detail: { title: 'Renamed' } }))"
    )

    expect(heading).to_have_text("Renamed")
