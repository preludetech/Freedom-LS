"""Tests for the `partials/messages.html` template.

Behavioural checks only — these intentionally do NOT assert on Tailwind
class names. They verify ARIA wiring, severity routing into the two live
regions, and the OOB attribute switching between full-page and HTMX modes.
"""

from __future__ import annotations

import re

import pytest

from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string


def _make_messages() -> list[Message]:
    return [
        Message(level=message_constants.SUCCESS, message="Saved"),
        Message(level=message_constants.INFO, message="Heads up"),
        Message(level=message_constants.WARNING, message="Careful"),
        Message(level=message_constants.ERROR, message="Boom"),
        Message(level=message_constants.DEBUG, message="Debug detail"),
    ]


@pytest.mark.django_db
class TestMessagesPartialFullPage:
    def test_renders_container_with_both_live_regions(
        self, mock_site_context: object
    ) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": _make_messages()},
        )

        assert 'id="toast-container"' in html
        assert 'id="toast-region-polite"' in html
        assert 'id="toast-region-assertive"' in html
        assert 'role="status"' in html
        assert 'role="alert"' in html
        assert 'aria-live="polite"' in html
        assert 'aria-live="assertive"' in html

    def test_live_regions_do_not_carry_aria_atomic_true(
        self, mock_site_context: object
    ) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": _make_messages()},
        )

        # The live region containers must not assert aria-atomic="true",
        # only the individual toast elements do (Bootstrap pitfall).
        polite_region = re.search(r'<div id="toast-region-polite"[^>]*>', html)
        assertive_region = re.search(r'<div id="toast-region-assertive"[^>]*>', html)
        assert polite_region is not None
        assert assertive_region is not None
        assert 'aria-atomic="true"' not in polite_region.group(0)
        assert 'aria-atomic="true"' not in assertive_region.group(0)
        # The regions are explicitly aria-atomic="false"
        assert 'aria-atomic="false"' in polite_region.group(0)
        assert 'aria-atomic="false"' in assertive_region.group(0)

    def test_each_toast_carries_aria_atomic_true(
        self, mock_site_context: object
    ) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": _make_messages()},
        )

        # Count toast elements and aria-atomic="true" occurrences.
        toast_count = len(re.findall(r'id="toast-[0-9a-f]+"', html))
        atomic_count = html.count('aria-atomic="true"')
        assert toast_count == 5
        assert atomic_count == toast_count

    def test_severity_routing_polite_vs_assertive(
        self, mock_site_context: object
    ) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": _make_messages()},
        )

        # Split the document into the two regions and check membership.
        polite_match = re.search(
            r'id="toast-region-polite"[^>]*>(.*?)</div>\s*<div id="toast-region-assertive"',
            html,
            re.DOTALL,
        )
        assertive_match = re.search(
            r'id="toast-region-assertive"[^>]*>(.*?)</div>\s*</div>',
            html,
            re.DOTALL,
        )
        assert polite_match is not None
        assert assertive_match is not None
        polite = polite_match.group(1)
        assertive = assertive_match.group(1)

        assert "Saved" in polite
        assert "Heads up" in polite
        assert "Careful" in polite
        assert "Debug detail" in polite
        assert "Boom" not in polite

        assert "Boom" in assertive
        assert "Saved" not in assertive
        assert "Heads up" not in assertive

    def test_close_button_label(self, mock_site_context: object) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": [Message(level=message_constants.SUCCESS, message="Hi")]},
        )

        assert 'aria-label="Dismiss notification"' in html

    def test_no_oob_attribute_in_full_page_mode(
        self, mock_site_context: object
    ) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": _make_messages()},
        )

        assert "hx-swap-oob" not in html


@pytest.mark.django_db
class TestMessagesPartialOob:
    def test_no_container_in_oob_mode(self, mock_site_context: object) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": _make_messages(), "oob": True},
        )

        assert 'id="toast-container"' not in html
        assert 'id="toast-region-polite"' not in html
        assert 'id="toast-region-assertive"' not in html

    def test_oob_attributes_per_severity(self, mock_site_context: object) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": _make_messages(), "oob": True},
        )

        polite_count = html.count('hx-swap-oob="beforeend:#toast-region-polite"')
        assertive_count = html.count('hx-swap-oob="beforeend:#toast-region-assertive"')

        # Four polite (success, info, warning, debug) and one assertive (error).
        assert polite_count == 4
        assert assertive_count == 1

    def test_each_oob_toast_has_unique_id(self, mock_site_context: object) -> None:
        html = render_to_string(
            "partials/messages.html",
            {"messages": _make_messages(), "oob": True},
        )

        ids = re.findall(r'id="(toast-[0-9a-f]+)"', html)
        assert len(ids) == 5
        assert len(set(ids)) == 5
