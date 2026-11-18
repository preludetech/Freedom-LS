"""Tests for lazy panels: the skeleton, the loaded body and the too-large message."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import time_machine

from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils import timezone

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.errors import PanelBodyTooLargeError
from freedom_ls.panel_framework.lazy_panels import (
    LOADED_PARAM,
    LazyBodyPanel,
    render_region,
)
from freedom_ls.panel_framework.views import SectionConfigBase

pytestmark = pytest.mark.django_db


class _StubLazyPanel(LazyBodyPanel):
    title = "Lazy"
    region_template_name = "panel_framework/test_lazy_region.html"
    load_label = "Load the stub"

    def get_loaded_context(self) -> dict[str, object]:
        return {"gathered": "gathered-value"}


class _TooLargePanel(_StubLazyPanel):
    def get_loaded_context(self) -> dict[str, object]:
        raise PanelBodyTooLargeError("Far too big to show.")


class _StampedPanel(_StubLazyPanel):
    show_as_of = True


class _StampedWithOwnTimePanel(_StampedPanel):
    def get_loaded_context(self) -> dict[str, object]:
        return {"as_of": datetime(2026, 1, 5, 8, 15, tzinfo=UTC)}


class _StampedNaivePanel(_StampedPanel):
    def get_loaded_context(self) -> dict[str, object]:
        return {"as_of": datetime.fromisoformat("2026-01-05T08:15:00")}


class _StampedNotYetComputedPanel(_StampedPanel):
    def get_loaded_context(self) -> dict[str, object]:
        return {"gathered": "gathered-value", "as_of": None}


class _StampedTooLargePanel(_StampedPanel):
    def get_loaded_context(self) -> dict[str, object]:
        raise PanelBodyTooLargeError("Far too big to show.")


def _render(panel_class: type[LazyBodyPanel], query: str = "") -> str:
    ctx = PanelContext(
        request=RequestFactory().get(f"/base{query}"),
        instance=None,
        base_url="/base",
        name="",
        config=SectionConfigBase,
    )
    return render_region(panel_class(ctx)).content.decode()


def test_the_first_render_is_a_busy_skeleton_that_fetches_the_body(
    mock_site_context: Site,
) -> None:
    html = _render(_StubLazyPanel)

    assert 'aria-busy="true"' in html
    assert f'hx-get="/base?{LOADED_PARAM}=1"' in html
    assert 'hx-trigger="load"' in html
    assert "gathered-value" not in html


def test_the_loaded_fetch_renders_the_body(mock_site_context: Site) -> None:
    html = _render(_StubLazyPanel, f"?{LOADED_PARAM}=1")

    assert "gathered-value" in html
    assert "aria-busy" not in html


def test_the_javascript_off_link_carries_the_load_label(
    mock_site_context: Site,
) -> None:
    html = _render(_StubLazyPanel)

    noscript = html.split("<noscript>")[1].split("</noscript>")[0]
    assert "Load the stub" in noscript
    assert f'href="/base?{LOADED_PARAM}=1"' in noscript


def test_a_body_too_large_to_show_gives_its_message_and_no_body(
    mock_site_context: Site,
) -> None:
    html = _render(_TooLargePanel, f"?{LOADED_PARAM}=1")

    assert "Far too big to show." in html
    assert "gathered-value" not in html


def test_the_full_panel_renders_its_region_inside_the_card(
    mock_site_context: Site,
) -> None:
    ctx = PanelContext(
        request=RequestFactory().get("/base"),
        instance=None,
        base_url="/base",
        name="",
        config=SectionConfigBase,
    )
    panel = _StubLazyPanel(ctx)

    html = render_to_string(
        panel.template_name, panel.get_context_data(), request=panel.request
    )

    assert 'aria-busy="true"' in html
    assert "Lazy" in html


LOADED_QUERY = f"?{LOADED_PARAM}=1"


def test_the_stamp_shows_the_render_time_in_the_active_zone(
    mock_site_context: Site,
) -> None:
    with (
        time_machine.travel(datetime(2026, 11, 3, 5, 37, tzinfo=UTC), tick=False),
        timezone.override("Africa/Johannesburg"),
    ):
        html = _render(_StampedPanel, LOADED_QUERY)

    assert "As of" in html
    assert "3 Nov 2026" in html
    assert "07:37" in html
    assert "SAST" in html
    assert 'datetime="2026-11-03T07:37:00+02:00"' in html


def test_a_value_returned_as_as_of_is_the_one_shown(mock_site_context: Site) -> None:
    with (
        time_machine.travel(datetime(2026, 11, 3, 5, 37, tzinfo=UTC), tick=False),
        timezone.override("Africa/Johannesburg"),
    ):
        html = _render(_StampedWithOwnTimePanel, LOADED_QUERY)

    assert 'datetime="2026-01-05T10:15:00+02:00"' in html
    assert "07:37" not in html


def test_a_naive_as_of_raises(mock_site_context: Site) -> None:
    with pytest.raises(ValueError, match="_StampedNaivePanel's as_of"):
        _render(_StampedNaivePanel, LOADED_QUERY)


def test_an_as_of_of_none_shows_the_body_without_a_stamp(
    mock_site_context: Site,
) -> None:
    html = _render(_StampedNotYetComputedPanel, LOADED_QUERY)

    assert "gathered-value" in html
    assert "As of" not in html


def test_the_skeleton_has_no_stamp(mock_site_context: Site) -> None:
    html = _render(_StampedPanel)

    assert "As of" not in html


def test_the_too_large_notice_has_no_stamp(mock_site_context: Site) -> None:
    html = _render(_StampedTooLargePanel, LOADED_QUERY)

    assert "Far too big to show." in html
    assert "As of" not in html


def test_a_panel_that_does_not_ask_for_the_stamp_shows_none(
    mock_site_context: Site,
) -> None:
    html = _render(_StubLazyPanel, LOADED_QUERY)

    assert "As of" not in html
