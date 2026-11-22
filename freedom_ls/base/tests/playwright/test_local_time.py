"""E2E tests for the localTime Alpine component's text format."""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.sites.models import Site

_TIME_ELEMENT = (
    '<time id="when" datetime="{instant}" x-data="localTime" '
    'data-show-zone="{show_zone}">server text</time>'
)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_local_time_uses_the_project_format_in_any_browser_locale(
    browser: Browser, live_server: LiveServer, live_server_site: Site
) -> None:
    """A localTime element reads "6 Nov 2026, 14:03" whatever the browser locale is.

    The component used to pass the browser's locale to Intl.DateTimeFormat, so an
    en-US browser showed "Nov 6, 2026, 02:03 PM". The zone is still the viewer's,
    and the short zone name is appended only when data-show-zone is "true".
    Each of en-US, de-DE and en-GB gets its own browser context.
    """
    for locale in ("en-US", "de-DE", "en-GB"):
        context = browser.new_context(locale=locale, timezone_id="UTC")
        page = context.new_page()
        try:
            page.goto(live_server.url)
            for show_zone, expected in (
                ("false", "6 Nov 2026, 14:03"),
                ("true", "6 Nov 2026, 14:03 UTC"),
            ):
                page.evaluate(
                    """([html]) => {
                        document.getElementById("when")?.remove();
                        const holder = document.createElement("div");
                        holder.innerHTML = html;
                        document.body.appendChild(holder.firstElementChild);
                    }""",
                    [
                        _TIME_ELEMENT.format(
                            instant="2026-11-06T14:03:00+00:00", show_zone=show_zone
                        )
                    ],
                )
                expect(
                    page.locator("#when"),
                    f"localTime text under {locale} with show-zone {show_zone}",
                ).to_have_text(expected)
        finally:
            context.close()
