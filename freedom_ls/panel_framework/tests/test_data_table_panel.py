"""A table panel refreshes its region, never its whole frame.

A sort, search or page click targets the panel's region id and gets back the
region template alone. Any other request for the panel's URL gets the whole
panel, frame and title included.
"""

from __future__ import annotations

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.test import RequestFactory

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import DataTablePanel

from .conftest import _make_stub
from .stub_panels import StubDataTable, StubDataTablePanel
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


def test_search_trigger_sets_replace_url(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x")

    response = fetch(
        _panel_path(stub.pk),
        data={"stub-q": "row"},
        htmx=True,
        hx_target=_region_id(),
        hx_trigger="stub-search",
    )

    assert "HX-Push-Url" not in response
    assert (
        response["HX-Replace-Url"]
        == f"/test-panel/framework/{_panel_path(stub.pk)}?stub-q=row"
    )


def test_sort_link_resets_page(mock_site_context: Site) -> None:
    stubs = [_make_stub(name=f"row-{i:02d}") for i in range(30)]

    html = fetch(
        f"stubs/{stubs[0].pk}/__tabs/pair", data={"a-page": "2"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    sort_links = [
        link
        for link in table_a.cssselect("a[href]")
        if "a-sort=name" in link.get("href", "")
    ]
    assert sort_links
    for link in sort_links:
        assert "a-page" not in link.get("href")


def test_search_text_is_url_encoded(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk), data={"stub-q": "a & b + c #"}).content.decode()

    document = lxml.html.fromstring(html)
    (search_input,) = document.cssselect("input[name='stub-q']")
    assert search_input.get("value") == "a & b + c #"
    (sort_link,) = [
        link
        for link in document.cssselect("a[href]")
        if "stub-sort=name" in link.get("href", "")
    ]
    href = sort_link.get("href")
    assert "stub-q=a" in href
    assert "%26" in href  # the encoded "&"
    assert "%2B" in href  # the encoded "+"
    assert "%23" in href  # the encoded "#"


class _NoSearchDataTable(StubDataTable):
    """The same rows and columns as StubDataTable, with no search box."""

    search_fields: list[str] = []


class _NoSearchTablePanel(DataTablePanel):
    title = "No search"
    data_table = _NoSearchDataTable
    table_key = "nosearch"


def _bind_table_panel(panel_class: type[DataTablePanel]) -> DataTablePanel:
    return panel_class(
        PanelContext(
            request=RequestFactory().get("/p"),
            instance=None,
            base_url="/p",
            name="",
            page_url="/p",
        )
    )


def test_a_table_without_search_fields_renders_no_search_input(
    mock_site_context: Site,
) -> None:
    panel = _bind_table_panel(_NoSearchTablePanel)

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    assert 'type="search"' not in html
    assert 'id="nosearch-table"' in html


def test_a_table_with_search_fields_renders_a_search_input(
    mock_site_context: Site,
) -> None:
    panel = _bind_table_panel(StubDataTablePanel)

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    assert 'type="search"' in html


def test_region_response_includes_announcement(mock_site_context: Site) -> None:
    stubs = [_make_stub(name=f"row-{i:02d}") for i in range(30)]

    html = fetch(
        _panel_path(stubs[0].pk), htmx=True, hx_target=_region_id()
    ).content.decode()

    assert 'hx-swap-oob="innerHTML:#scope-announcer"' in html
    assert "Showing 1\u201325 of 30" in html
    assert ", sorted by" not in html


def test_region_response_announcement_includes_sort(mock_site_context: Site) -> None:
    stubs = [_make_stub(name=f"row-{i:02d}") for i in range(30)]

    html = fetch(
        _panel_path(stubs[0].pk),
        data={"stub-sort": "name"},
        htmx=True,
        hx_target=_region_id(),
    ).content.decode()

    assert "Showing 1\u201325 of 30, sorted by Name" in html


def test_region_response_announcement_with_no_rows(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(
        _panel_path(stub.pk),
        data={"stub-q": "no-match"},
        htmx=True,
        hx_target=_region_id(),
    ).content.decode()

    assert "No results" in html


def test_plain_get_has_no_announcer_fragment(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert "hx-swap-oob" not in html


def test_search_form_hidden_inputs_carry_other_state(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x")

    html = fetch(
        _panel_path(stub.pk), data={"stub-sort": "name", "b-page": "2"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (form,) = document.cssselect("#stub-search")
    names = [element.get("name") for element in form.cssselect("input[type='hidden']")]
    assert names.count("stub-sort") == 1
    assert "stub-q" not in names
    assert "stub-page" not in names
    assert "b-page" in names
    assert len(names) == len(set(names))
