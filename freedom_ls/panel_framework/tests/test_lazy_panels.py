"""Tests for lazy panels: the skeleton, the loaded body and the too-large message."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.test import RequestFactory

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
