"""Tests for DataTablePanel.render() chrome behaviour.

These tests pin the rule: panel chrome (the ``<section class="surface">``
wrapper plus the ``<h2>`` title) is stripped only when the HTMX swap is
targeting the panel's own content container — i.e. an internal sort,
search, or pagination action. Tab-click and instance-load HTMX requests
must keep the chrome.
"""

from __future__ import annotations

import pytest

from django.test import RequestFactory

from .conftest import _make_stub, make_staff_user
from .stub_panels import StubDataTablePanel


@pytest.mark.django_db
def test_render_keeps_chrome_when_hx_target_is_not_panel_table(
    mock_site_context,
) -> None:
    """A tab-click HTMX request targets the tab-content div, not the table.
    Chrome must survive."""
    instance = _make_stub(name="row-x")
    panel = StubDataTablePanel(instance)
    request = RequestFactory().get(
        "/", HTTP_HX_REQUEST="true", HTTP_HX_TARGET="tab-content-details"
    )
    request.user = make_staff_user()

    html = panel.render(request, base_url="/x", panel_name="default")

    assert "<section" in html
    assert 'data-panel="default"' in html
    assert "<h2>Stub</h2>" in html


@pytest.mark.django_db
def test_render_strips_chrome_when_hx_target_is_panel_table(
    mock_site_context,
) -> None:
    """A panel-internal swap (sort/search/pagination) targets the table id.
    Chrome must be stripped to avoid nested wrappers."""
    instance = _make_stub(name="row-x")
    panel = StubDataTablePanel(instance)
    request = RequestFactory().get(
        "/", HTTP_HX_REQUEST="true", HTTP_HX_TARGET="table-default"
    )
    request.user = make_staff_user()

    html = panel.render(request, base_url="/x", panel_name="default")

    assert "<section" not in html
    assert "<h2>Stub</h2>" not in html


@pytest.mark.django_db
def test_render_keeps_chrome_on_full_page_load(mock_site_context) -> None:
    """Plain non-HTMX GET keeps chrome (instance page load)."""
    instance = _make_stub(name="row-x")
    panel = StubDataTablePanel(instance)
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    html = panel.render(request, base_url="/x", panel_name="default")

    assert "<section" in html
    assert "<h2>Stub</h2>" in html


@pytest.mark.django_db
def test_render_keeps_chrome_when_hx_request_but_no_target(
    mock_site_context,
) -> None:
    """If HTMX sends no HX-Target header, the swap is not panel-internal —
    keep chrome."""
    instance = _make_stub(name="row-x")
    panel = StubDataTablePanel(instance)
    request = RequestFactory().get("/", HTTP_HX_REQUEST="true")
    request.user = make_staff_user()

    html = panel.render(request, base_url="/x", panel_name="default")

    assert "<section" in html
    assert "<h2>Stub</h2>" in html
