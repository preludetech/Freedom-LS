"""A table panel refreshes its region, never its whole frame.

A sort, search or page click targets the panel's region id and gets back the
region template alone. Any other request for the panel's URL gets the whole
panel, frame and title included.
"""

from __future__ import annotations

import lxml.html
import pytest

from django.contrib.sites.models import Site

from .conftest import _make_stub
from .view_helpers import fetch

pytestmark = pytest.mark.django_db


def _panel_path(stub_pk: object) -> str:
    return f"stubs/{stub_pk}/__tabs/default"


def _region_id() -> str:
    return "stub-table"


def test_a_request_targeting_the_region_gets_the_table_without_the_frame(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(
        _panel_path(stub.pk), htmx=True, hx_target=_region_id()
    ).content.decode()

    assert f'id="{_region_id()}"' in html
    assert "row-x" in html
    assert "<section" not in html
    assert "<h2>Stub</h2>" not in html


def test_a_plain_get_keeps_the_frame(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert 'data-panel="default"' in html
    assert "<h2>Stub</h2>" in html


def test_the_frame_refetches_its_own_region_on_panel_changed(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert 'hx-trigger="panelChanged from:body"' in html
    assert f'hx-target="#{_region_id()}"' in html
    assert f'hx-get="/test-panel/framework/{_panel_path(stub.pk)}"' in html


def test_two_tables_page_independently(mock_site_context: Site) -> None:
    stubs = [_make_stub(name=f"row-{i:02d}") for i in range(30)]

    html = fetch(
        f"stubs/{stubs[0].pk}/__tabs/pair", data={"a-page": "2"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    (table_b,) = document.cssselect("#b-table")
    assert "row-25" in table_a.text_content()
    assert "row-29" in table_a.text_content()
    assert "row-00" not in table_a.text_content()
    assert "row-00" in table_b.text_content()
    assert "row-24" in table_b.text_content()
    assert "row-25" not in table_b.text_content()


def test_links_keep_other_tables_state(mock_site_context: Site) -> None:
    stubs = [_make_stub(name=f"row-{i:02d}") for i in range(30)]

    html = fetch(
        f"stubs/{stubs[0].pk}/__tabs/pair", data={"b-page": "2", "extra": "1"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    page_links = [
        link
        for link in table_a.cssselect("a[href]")
        if "a-page=" in link.get("href", "")
    ]
    assert page_links
    for link in page_links:
        href = link.get("href")
        assert "b-page=2" in href
        assert "extra=1" in href


def test_region_response_sets_push_url_to_page_url(mock_site_context: Site) -> None:
    stubs = [_make_stub(name=f"row-{i:02d}") for i in range(30)]
    pk = stubs[0].pk

    response = fetch(
        f"stubs/{pk}/__tabs/pair/__panels/a",
        data={"a-page": "2"},
        htmx=True,
        hx_target="a-table",
    )

    assert (
        response["HX-Push-Url"]
        == f"/test-panel/framework/stubs/{pk}/__tabs/pair?a-page=2"
    )
    document = lxml.html.fromstring(response.content.decode())
    (page_one_link,) = [
        link
        for link in document.cssselect("a[href]")
        if "a-page=1" in link.get("href", "") and link.text_content().strip() == "1"
    ]
    assert page_one_link.get("href").startswith(
        f"/test-panel/framework/stubs/{pk}/__tabs/pair"
    )
    assert page_one_link.get("hx-get").startswith(
        f"/test-panel/framework/stubs/{pk}/__tabs/pair/__panels/a"
    )


def test_plain_get_renders_pushed_state(mock_site_context: Site) -> None:
    stubs = [_make_stub(name=f"row-{i:02d}") for i in range(30)]
    pk = stubs[0].pk

    html = fetch(f"stubs/{pk}/__tabs/pair", data={"a-page": "2"}).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    assert "row-29" in table_a.text_content()
    assert "row-00" not in table_a.text_content()
    assert 'data-panel="a"' in html
