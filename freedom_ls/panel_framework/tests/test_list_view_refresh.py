"""Tests for list-view table refresh (Bug 3: 'Save and add another' table refresh).

TDD: these tests are written first. They exercise:
1. The server-side HX-Target short-circuit in _render_list_view_content.
2. The listRefresh listener wiring emitted on a normal (non-HTMX) list GET.
"""

from __future__ import annotations

import pytest

from django.test import RequestFactory

from .conftest import _make_stub, make_staff_user
from .stub_panels import StubListConfig

# ---------------------------------------------------------------------------
# Test 1 — server-side short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_htmx_target_table_returns_only_table_html(mock_site_context) -> None:
    """GET the list URL with HX-Target: data-table-container returns only the
    table, not the create-action button/modal.

    Proves Piece 1: the short-circuit in _render_list_view_content.
    """
    _make_stub(name="row-1")
    user = make_staff_user()

    rf = RequestFactory()
    request = rf.get(
        "/test-panel/framework/stubs/",
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="data-table-container",
    )
    request.user = user

    from freedom_ls.panel_framework.views import _render_list_view_content

    html = _render_list_view_content(
        request, StubListConfig, "/test-panel/framework/stubs/"
    )

    # Must contain the table container
    assert 'id="data-table-container"' in html
    # Must NOT contain the create-action button/modal — short-circuit must skip actions
    assert "Create Item" not in html


# ---------------------------------------------------------------------------
# Test 2 — listener wiring
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_normal_get_includes_list_refresh_wiring(mock_site_context) -> None:
    """A normal (non-HTMX) GET to the list URL includes listRefresh Alpine wiring.

    Proves Piece 2: the wrapper partial with x-data, data-refresh-events, and
    data-refresh-target is present in the rendered HTML, and there is exactly
    one x-data="listRefresh" element (no double-listener accumulation).
    """
    _make_stub(name="row-2")
    user = make_staff_user()

    rf = RequestFactory()
    request = rf.get("/test-panel/framework/stubs/")
    request.user = user

    from freedom_ls.panel_framework.views import _render_list_view_content

    html = _render_list_view_content(
        request, StubListConfig, "/test-panel/framework/stubs/"
    )

    # Must contain the Alpine listRefresh component
    assert 'x-data="listRefresh"' in html
    # Must carry the created event name
    assert "itemCreated" in html
    # Must carry the correct refresh target
    assert 'data-refresh-target="data-table-container"' in html
    # Exactly ONE listRefresh wrapper — no accumulation
    assert html.count('x-data="listRefresh"') == 1
