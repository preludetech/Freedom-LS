"""A table panel refreshes its region, never its whole frame.

A sort, search or page click targets the panel's region id and gets back the
region template alone. Any other request for the panel's URL gets the whole
panel, frame and title included.
"""

from __future__ import annotations

import pytest

from .conftest import _make_stub
from .view_helpers import fetch

pytestmark = pytest.mark.django_db


def _panel_path(stub_pk: object) -> str:
    return f"stubs/{stub_pk}/__tabs/default"


def _region_id(stub_pk: object) -> str:
    return f"panel-test-panel-framework-stubs-{stub_pk}-__tabs-default"


def test_a_request_targeting_the_region_gets_the_table_without_the_frame(
    mock_site_context,
) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(
        _panel_path(stub.pk), htmx=True, hx_target=_region_id(stub.pk)
    ).content.decode()

    assert f'id="{_region_id(stub.pk)}"' in html
    assert "row-x" in html
    assert "<section" not in html
    assert "<h2>Stub</h2>" not in html


def test_a_plain_get_keeps_the_frame(mock_site_context) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert 'data-panel="default"' in html
    assert "<h2>Stub</h2>" in html


def test_the_frame_refetches_its_own_region_on_panel_changed(
    mock_site_context,
) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert 'hx-trigger="panelChanged from:body"' in html
    assert f'hx-target="#{_region_id(stub.pk)}"' in html
    assert f'hx-get="/test-panel/framework/{_panel_path(stub.pk)}"' in html
