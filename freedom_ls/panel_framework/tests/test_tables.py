"""Tests for data tables: query parsing, columns, region refreshes, filters, the
mobile card layout and the CSV export."""

from __future__ import annotations

import csv
import io
import re

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.db.models import QuerySet
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    QueryDict,
    StreamingHttpResponse,
)
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.utils import timezone

from freedom_ls.panel_framework.bulk_actions import BulkAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.filters import ChoiceFilter, TableFilter
from freedom_ls.panel_framework.panels import DataTablePanel
from freedom_ls.panel_framework.tables import Column, DataTable, ExportColumn
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    ListViewConfig,
    NavGroup,
    SectionConfig,
    SectionConfigBase,
)
from freedom_ls.tests.site_context import drop_ambient_request

from .helpers import make_stub
from .stub_panels import (
    StubBulkAction,
    StubDataTable,
    StubDataTablePanel,
    StubDetailDataTable,
    StubPlainDataTable,
)
from .view_helpers import call_view, fetch, make_request

pytestmark = pytest.mark.django_db


def test_table_query_to_params_round_trips() -> None:
    request = RequestFactory().get("/", {"stub-page": "3", "stub-zzz": "nope"})

    query = StubDataTable.parse_query(request, "stub")

    assert query.to_params() == {"stub-page": ["3"]}


def test_invalid_sort_is_ignored() -> None:
    request = RequestFactory().get("/", {"stub-sort": "nope"})

    query = StubDataTable.parse_query(request, "stub")

    assert query.sort == ""


def test_column_derives_sort_field() -> None:
    column = Column("N", "t", text_attr="user.name", sortable=True)

    assert column.sort_field == "user__name"


def test_a_column_with_a_url_is_a_link() -> None:
    column = Column(
        header="Name",
        template_name="cotton/data-table-cells/link.html",
        text_attr="name",
        url_name="panel_framework_test:framework",
        url_path_template="stubs/{pk}",
    )

    assert column.is_link is True


def test_a_column_with_no_url_is_not_a_link() -> None:
    column = Column(
        header="Name", template_name="cotton/data-table-cells/text.html", attr="name"
    )

    assert column.is_link is False


def test_a_table_shows_ten_rows_a_page_by_default() -> None:
    """Few enough that the pager sits on screen below the table."""
    assert DataTable.page_size == 10


# A table panel refreshes its region, never its whole frame.
#
# A sort, search or page click targets the panel's region id and gets back the
# region template alone. Any other request for the panel's URL gets the whole
# panel, frame and title included.


# Enough rows for a second page, whatever the page size.
_PAGE_SIZE = StubDataTable.page_size
_ROWS = _PAGE_SIZE + 5


def _panel_path(stub_pk: object) -> str:
    return f"stubs/{stub_pk}/__tabs/default"


def _region_id() -> str:
    return "stub-table"


def test_a_request_targeting_the_region_gets_the_table_without_the_frame(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-x")

    html = fetch(
        _panel_path(stub.pk), htmx=True, hx_target=_region_id()
    ).content.decode()

    assert f'id="{_region_id()}"' in html
    assert "row-x" in html
    assert "<section" not in html
    assert ">Stub</h2>" not in html


def test_a_plain_get_keeps_the_frame(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert 'data-panel="default"' in html
    assert ">Stub</h2>" in html


def test_the_frame_refetches_its_own_region_on_the_stubs_declared_event(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert 'hx-trigger="itemChanged from:body"' in html
    assert f'hx-target="#{_region_id()}"' in html
    assert f'hx-get="/test-panel/framework/{_panel_path(stub.pk)}"' in html


def test_two_tables_page_independently(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(_ROWS)]

    html = fetch(
        f"stubs/{stubs[0].pk}/__tabs/pair", data={"a-page": "2"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    (table_b,) = document.cssselect("#b-table")
    assert f"row-{_PAGE_SIZE:02d}" in table_a.text_content()
    assert f"row-{_ROWS - 1:02d}" in table_a.text_content()
    assert "row-00" not in table_a.text_content()
    assert "row-00" in table_b.text_content()
    assert f"row-{_PAGE_SIZE - 1:02d}" in table_b.text_content()
    assert f"row-{_PAGE_SIZE:02d}" not in table_b.text_content()


def test_links_keep_other_tables_state(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]

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
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]
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


def _fetch_pair_region_a(
    pk: object, data: dict[str, str], current_url: str
) -> tuple[str, lxml.html.HtmlElement]:
    response = fetch(
        f"stubs/{pk}/__tabs/pair/__panels/a",
        data=data,
        htmx=True,
        hx_target="a-table",
        current_url=current_url,
    )
    return response["HX-Push-Url"], lxml.html.fromstring(response.content.decode())


def _a_page_link_hrefs(document: lxml.html.HtmlElement) -> list[str]:
    hrefs = [
        link.get("href")
        for link in document.cssselect("a[href]")
        if "a-page=" in link.get("href", "")
    ]
    assert hrefs
    return hrefs


def test_region_request_takes_sibling_state_from_current_url(
    mock_site_context: Site,
) -> None:
    """Table a's links were rendered before table b moved to page 2, so they
    still say b-page=1; the browser's current URL has b's live state."""
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]
    pk = stubs[0].pk
    page_url = f"http://testserver/test-panel/framework/stubs/{pk}/__tabs/pair"

    push_url, document = _fetch_pair_region_a(
        pk,
        data={"a-page": "2", "b-page": "1"},
        current_url=f"{page_url}?a-page=1&b-page=2&extra=1",
    )

    assert "a-page=2" in push_url
    assert "b-page=2" in push_url
    assert "extra=1" in push_url
    assert "b-page=1" not in push_url
    for href in _a_page_link_hrefs(document):
        assert "b-page=2" in href
        assert "extra=1" in href


def test_region_request_ignores_current_url_for_another_page(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]
    pk = stubs[0].pk

    push_url, document = _fetch_pair_region_a(
        pk,
        data={"a-page": "2", "b-page": "1"},
        current_url=f"http://testserver/test-panel/framework/stubs/{pk}/__tabs/default?b-page=2",
    )

    assert "b-page=1" in push_url
    assert "b-page=2" not in push_url
    for href in _a_page_link_hrefs(document):
        assert "b-page=2" not in href


def test_region_response_replaces_history_when_url_is_unchanged(
    mock_site_context: Site,
) -> None:
    """A refresh that lands on the URL already in the address bar must not
    stack a duplicate history entry, nor touch history at all: any history
    update closes an open modal or quick view."""
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]
    pk = stubs[0].pk
    page_url = f"/test-panel/framework/stubs/{pk}/__tabs/pair"

    response = fetch(
        f"stubs/{pk}/__tabs/pair/__panels/a",
        data={"a-page": "2"},
        htmx=True,
        hx_target="a-table",
        current_url=f"http://testserver{page_url}?a-page=2",
    )

    assert response["HX-Replace-Url"] == "false"
    assert "HX-Push-Url" not in response


def test_region_response_treats_a_trailing_slash_as_the_same_url(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]
    pk = stubs[0].pk
    page_url = f"/test-panel/framework/stubs/{pk}/__tabs/pair"

    response = fetch(
        f"stubs/{pk}/__tabs/pair/__panels/a",
        htmx=True,
        hx_target="a-table",
        current_url=f"http://testserver{page_url}/",
    )

    assert response["HX-Replace-Url"] == "false"
    assert "HX-Push-Url" not in response


def test_plain_get_renders_pushed_state(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(_ROWS)]
    pk = stubs[0].pk

    html = fetch(f"stubs/{pk}/__tabs/pair", data={"a-page": "2"}).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    assert f"row-{_ROWS - 1:02d}" in table_a.text_content()
    assert "row-00" not in table_a.text_content()
    assert 'data-panel="a"' in html


def test_search_trigger_sets_replace_url(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

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


def test_pagination_links_in_a_sorted_region_response_keep_the_sort(
    client: Client, mock_site_context: Site
) -> None:
    for i in range(StubDataTable.page_size + 2):
        make_stub(name=f"row-{i:02d}")

    response = client.get(
        "/test-panel/framework/stubs/",
        {"stubs-sort": "name"},
        headers={"HX-Request": "true", "HX-Target": "stubs-table"},
    )

    document = lxml.html.fromstring(response.content.decode())
    (page_two_link,) = [
        link
        for link in document.cssselect("#stubs-table a[href]")
        if link.text_content().strip() == "2"
    ]
    assert "stubs-sort=name" in page_two_link.get("href")
    assert "stubs-page=2" in page_two_link.get("href")


def test_sort_link_resets_page(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]

    html = fetch(
        f"stubs/{stubs[0].pk}/__tabs/pair", data={"a-page": "2"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    sort_links = [
        link
        for link in table_a.cssselect("a[href]")
        if "a-sort=-name" in link.get("href", "")
    ]
    assert sort_links
    for link in sort_links:
        assert "a-page" not in link.get("href")


def test_search_text_is_url_encoded(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk), data={"stub-q": "a & b + c #"}).content.decode()

    document = lxml.html.fromstring(html)
    # The mobile sheet also carries the search text as a hidden input, so its
    # value round-trips through a "Show results" submit; select the visible
    # search box specifically.
    (search_input,) = document.cssselect("input[type='search'][name='stub-q']")
    assert search_input.get("value") == "a & b + c #"
    (sort_link,) = [
        link
        for link in document.cssselect("thead a[href]")
        if "stub-sort=-name" in link.get("href", "")
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


class _ExportOnlyDataTable(_NoSearchDataTable):
    """Nothing for the desktop toolbar but the export link: no search, no
    filters and no sort applied."""

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return []

    @staticmethod
    def get_export_columns() -> list[ExportColumn]:
        return [ExportColumn("Name", "name")]


class _ExportOnlyTablePanel(DataTablePanel):
    title = "Export only"
    data_table = _ExportOnlyDataTable
    table_key = "exportonly"


class _CountingFilter(ChoiceFilter):
    """Counts `get_choices` calls, standing in for a filter whose choices
    come from a query."""

    calls = 0

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        type(self).calls += 1
        return [("a", "A"), ("b", "B")]


class _CountingDataTable(_NoSearchDataTable):
    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [_CountingFilter("kind", "Kind", lookup="kind")]


class _CountingTablePanel(DataTablePanel):
    title = "Counting"
    data_table = _CountingDataTable
    table_key = "counting"


def test_a_filters_choices_are_fetched_once_per_request(
    mock_site_context: Site,
) -> None:
    _CountingFilter.calls = 0
    panel = _bind_table_panel(_CountingTablePanel)

    panel.get_context_data()

    assert _CountingFilter.calls == 1


def _bind_table_panel(panel_class: type[DataTablePanel]) -> DataTablePanel:
    return panel_class(
        PanelContext(
            request=RequestFactory().get("/p"),
            instance=None,
            base_url="/p",
            name="",
            config=SectionConfigBase,
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
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(_ROWS)]

    html = fetch(
        _panel_path(stubs[0].pk), htmx=True, hx_target=_region_id()
    ).content.decode()

    assert 'hx-swap-oob="innerHTML:#scope-announcer"' in html
    # The stub names Name as its default sort, so it reads as sorted from the start.
    assert f"Showing 1\u2013{_PAGE_SIZE} of {_ROWS}, sorted by Name" in html


def test_region_response_announcement_includes_sort(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(_ROWS)]

    html = fetch(
        _panel_path(stubs[0].pk),
        data={"stub-sort": "name"},
        htmx=True,
        hx_target=_region_id(),
    ).content.decode()

    assert f"Showing 1\u2013{_PAGE_SIZE} of {_ROWS}, sorted by Name" in html


def test_region_response_announcement_with_no_rows(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    html = fetch(
        _panel_path(stub.pk),
        data={"stub-q": "no-match"},
        htmx=True,
        hx_target=_region_id(),
    ).content.decode()

    assert "No results" in html


def test_plain_get_has_no_announcer_fragment(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert "hx-swap-oob" not in html


def test_search_form_hidden_inputs_carry_other_state(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

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


def test_invalid_filter_value_is_dropped(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk), data={"stub-kind": "zzz"}).content.decode()

    assert "row-x" in html
    assert 'aria-label="Remove Kind filter"' not in html


def test_filter_link_resets_page(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]

    html = fetch(
        f"stubs/{stubs[0].pk}/__tabs/pair", data={"a-page": "2"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    filter_links = [
        link
        for link in table_a.cssselect("a[href]")
        if "a-kind=a" in link.get("href", "")
    ]
    assert filter_links
    for link in filter_links:
        assert "a-page" not in link.get("href")


def test_filter_links_keep_other_tables_state(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(30)]

    html = fetch(
        f"stubs/{stubs[0].pk}/__tabs/pair", data={"b-kind": "a"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    filter_links = [
        link
        for link in table_a.cssselect("a[href]")
        if "a-kind=" in link.get("href", "")
    ]
    assert filter_links
    for link in filter_links:
        assert "b-kind=a" in link.get("href")


def test_clear_all_keeps_search_and_sort(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x", kind="a")

    html = fetch(
        _panel_path(stub.pk),
        data={"stub-sort": "name", "stub-q": "row", "stub-kind": "a"},
    ).content.decode()

    document = lxml.html.fromstring(html)
    (clear_link,) = [
        link
        for link in document.cssselect("a[href]")
        if link.text_content().strip() == "Clear all"
    ]
    href = clear_link.get("href")
    assert "stub-sort=name" in href
    assert "stub-q=row" in href
    assert "stub-kind" not in href


def test_search_input_keeps_its_id_and_name_and_has_a_label(
    mock_site_context: Site,
) -> None:
    panel = _bind_table_panel(StubDataTablePanel)

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    document = lxml.html.fromstring(html)
    (search_input,) = document.cssselect('input[type="search"]')
    assert search_input.get("id") == "stub-q"
    assert search_input.get("name") == "stub-q"
    assert document.cssselect('label[for="stub-q"]')


def test_a_table_with_nothing_for_a_toolbar_renders_no_toolbar_form(
    mock_site_context: Site,
) -> None:
    panel = _bind_table_panel(_NoSearchTablePanel)

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    document = lxml.html.fromstring(html)
    assert not document.cssselect("form#nosearch-search")
    assert not document.cssselect('input[type="search"]')


# Below md a table renders its rows as cards instead of a <table>, and its
# toolbar collapses to a search box, applied-filter chips and Filter/Sort
# buttons that open a shared filter-and-sort sheet.


def test_cards_render_primary_and_secondary_columns(mock_site_context: Site) -> None:
    make_stub(name="row-x", kind="a")

    html = fetch(_panel_path(make_stub(name="row-y", kind="b").pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    cards = table.cssselect("ul li")
    assert cards
    card_texts = [card.text_content() for card in cards]
    assert any("row-x" in text and "Alpha" in text for text in card_texts)
    assert any("row-y" in text and "Beta" in text for text in card_texts)


def test_cards_align_their_selection_checkbox_with_the_top_line(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-x", kind="a")

    html = fetch(_panel_path(make_stub(name="row-y", kind="b").pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    card = table.cssselect("ul li")[0]
    assert "items-start" in card.get("class").split()


def test_md_only_columns_are_omitted_from_cards(mock_site_context: Site) -> None:
    stub = make_stub(name="row-z", sat_score=4321)

    html = fetch(_panel_path(stub.pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    (card,) = table.cssselect("ul li")
    assert "4321" not in card.text_content()
    (row,) = table.cssselect("table tbody tr")
    assert "4321" in row.text_content()


def test_card_template_override_is_used(mock_site_context: Site) -> None:
    stub = make_stub(name="row-custom")

    html = fetch(f"stubs/{stub.pk}/__tabs/cards").content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#cards-table")
    assert "Custom card for row-custom" in table.text_content()


def test_sheet_hidden_inputs_carry_other_state(mock_site_context: Site) -> None:
    stub = make_stub(name="row-00")

    html = fetch(
        f"stubs/{stub.pk}/__tabs/pair",
        data={"a-sort": "name", "a-page": "2", "a-kind": "a", "b-page": "2"},
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    (sheet,) = table_a.cssselect("dialog#a-sheet")
    hidden_names = [
        field.get("name") for field in sheet.cssselect('input[type="hidden"]')
    ]
    assert "a-sort" not in hidden_names
    assert "a-page" not in hidden_names
    assert "a-kind" not in hidden_names
    assert "b-page" in hidden_names


def test_filter_and_sort_buttons_render_only_when_declared(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-00")

    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    (table_b,) = document.cssselect("#b-table")
    assert table_a.xpath(".//button[normalize-space()='Filter']")
    assert table_a.xpath(".//button[normalize-space()='Sort']")
    assert not table_b.xpath(".//button[normalize-space()='Filter']")
    assert not table_b.xpath(".//button[normalize-space()='Sort']")


def test_card_secondary_values_are_labelled_with_their_column_header(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-labelled", kind="a")

    html = fetch(_panel_path(stub.pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    (card,) = table.cssselect("ul li")
    pairs = [
        (term.text_content().strip(), term.getnext().text_content().strip())
        for term in card.cssselect("dl dt")
    ]
    assert pairs == [("Kind", "Alpha")]
    assert "Name" not in card.text_content()


def test_card_primary_line_ends_with_a_decorative_open_page_icon(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-open-page", kind="a")

    html = fetch(_panel_path(stub.pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    (card,) = table.cssselect("ul li")
    (primary_line,) = card.cssselect("[data-card-primary-line]")
    (decoration,) = primary_line.xpath("./*[last()][@aria-hidden='true']")
    assert decoration.cssselect("svg")
    assert "row-open-page" in primary_line.text_content()
    assert not card.xpath("./*[@aria-hidden='true']")


def test_a_card_whose_primary_column_is_plain_text_draws_no_open_page_icon(
    mock_site_context: Site,
) -> None:
    """The icon promises a page to open; table b's name column is text."""
    stub = make_stub(name="row-plain", kind="a")

    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#b-table")
    (card,) = table.cssselect("ul li")
    (primary_line,) = card.cssselect("[data-card-primary-line]")
    assert "row-plain" in primary_line.text_content()
    assert not primary_line.cssselect("svg")
    assert not primary_line.xpath("./*[@aria-hidden='true']")


def test_sheet_legends_drop_the_base_legend_padding(mock_site_context: Site) -> None:
    stub = make_stub(name="row-00")

    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()

    document = lxml.html.fromstring(html)
    (sheet,) = document.cssselect("#a-table dialog#a-sheet")
    legends = sheet.cssselect("fieldset legend")
    assert legends
    assert all("px-0" in legend.get("class").split() for legend in legends)


def test_sheet_renders_reset_legends_and_footer_buttons(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-00")

    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()

    document = lxml.html.fromstring(html)
    (sheet,) = document.cssselect("#a-table dialog#a-sheet")
    assert sheet.xpath(".//a[normalize-space()='Reset']")
    legends = sheet.cssselect("fieldset legend")
    assert legends
    assert "Sort" not in [legend.text_content().strip() for legend in legends]
    assert not sheet.cssselect("input[type='radio']")
    assert sheet.xpath(".//button[@type='button'][normalize-space()='Cancel']")
    assert sheet.xpath(".//button[@type='submit'][normalize-space()='Show results']")


def test_the_phone_sort_menu_lists_each_sortable_column_with_the_headers_link(
    mock_site_context: Site,
) -> None:
    """Sorting on a phone is a menu of columns, not a list of ascending and
    descending pairs; each entry carries the same URL as the column header,
    so choosing the active column flips its direction."""
    stub = make_stub(name="row-00")

    html = fetch(
        f"stubs/{stub.pk}/__tabs/pair", data={"a-sort": "name"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#a-table")
    items = table.cssselect("[role='menu'][aria-label='Sort by'] a[role='menuitem']")
    header_links = {
        a.text_content().strip(): a.get("href") for a in table.cssselect("thead th a")
    }
    assert [item.text_content().strip() for item in items] == list(header_links)
    assert [item.get("href") for item in items] == list(header_links.values())
    (active,) = [item for item in items if item.get("aria-current") == "true"]
    assert active.text_content().strip() == "Name"
    assert active.cssselect("svg[data-icon='sort_asc']")


def test_reset_in_the_sheet_keeps_the_sort(mock_site_context: Site) -> None:
    stub = make_stub(name="row-00")

    html = fetch(
        f"stubs/{stub.pk}/__tabs/pair", data={"a-sort": "-name", "a-kind": "a"}
    ).content.decode()

    document = lxml.html.fromstring(html)
    (reset,) = document.cssselect("#a-table dialog#a-sheet a[href]")
    assert "a-sort=-name" in reset.get("href")
    assert "a-kind" not in reset.get("href")


@pytest.mark.parametrize(
    ("path", "sheet_id", "title"),
    [
        ("__tabs/pair", "a-sheet", "Filter"),
        ("__tabs/children", "children-sheet", "Filter"),
    ],
)
def test_sheet_title_follows_the_controls_it_holds(
    mock_site_context: Site, path: str, sheet_id: str, title: str
) -> None:
    # The children table's Parent filter lists "in-scope" stubs only.
    stub = make_stub(name="in-scope-00")

    html = fetch(f"stubs/{stub.pk}/{path}").content.decode()

    document = lxml.html.fromstring(html)
    (sheet,) = document.cssselect(f"dialog#{sheet_id}")
    assert sheet.get("aria-label") == title
    assert sheet.cssselect("h2")[0].text_content().strip() == title


def test_a_table_with_sort_but_no_filters_renders_a_sort_menu_and_no_sheet(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-00")

    html = fetch(f"stubs/{stub.pk}/__tabs/sortonly").content.decode()

    document = lxml.html.fromstring(html)
    assert not document.cssselect("dialog#sortonly-sheet")
    assert document.cssselect("#sortonly-table [role='menu'][aria-label='Sort by']")
    assert not document.xpath("//button[normalize-space()='Filter']")


# A table that declares export columns serves a streamed, formula-safe CSV
# of its rows, honouring search, filters and sort but never pagination.


def _rows(response: HttpResponse | StreamingHttpResponse) -> list[list[str]]:
    assert isinstance(response, StreamingHttpResponse)
    body = b"".join(response.streaming_content).decode("utf-8")
    return list(csv.reader(io.StringIO(body.removeprefix("\ufeff"))))


def test_export_honours_search_filters_and_sort_without_pagination(
    mock_site_context: Site,
) -> None:
    kinds = ["b" if i % 3 else "a" for i in range(60)]
    stubs = [make_stub(name=f"row-{i:02d}", kind=kind) for i, kind in enumerate(kinds)]
    expected_names = sorted(
        (f"row-{i:02d}" for i, kind in enumerate(kinds) if kind == "b"),
        reverse=True,
    )
    assert len(expected_names) > 25  # more than one page, to prove paging is ignored

    response = fetch(
        _panel_path(stubs[0].pk),
        data={
            "stub-q": "row",
            "stub-kind": "b",
            "stub-sort": "-name",
            "stub-page": "2",
            "stub-export": "csv",
        },
    )

    header, *body = _rows(response)
    assert header == ["Name", "Kind"]
    assert [row[0] for row in body] == expected_names
    assert all(row[1] == "Beta" for row in body)


def test_formula_cells_escaped(mock_site_context: Site) -> None:
    stub = make_stub(name="=cmd", kind="a")

    response = fetch(_panel_path(stub.pk), data={"stub-export": "csv"})

    header, (name_cell, kind_cell) = _rows(response)
    assert header == ["Name", "Kind"]
    assert name_cell == "'=cmd"
    assert kind_cell == "Alpha"


def test_full_width_formula_cells_escaped(mock_site_context: Site) -> None:
    stub = make_stub(name="\uff1dcmd", kind="a")

    response = fetch(_panel_path(stub.pk), data={"stub-export": "csv"})

    _header, (name_cell, _kind_cell) = _rows(response)
    assert name_cell == "'\uff1dcmd"


def test_bom_and_headers(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x", kind="a")

    response = fetch(_panel_path(stub.pk), data={"stub-export": "csv"})

    assert response["Content-Type"] == "text/csv; charset=utf-8"
    today = timezone.localdate().isoformat()
    expected_disposition = f'attachment; filename="stub-{today}.csv"'
    assert response["Content-Disposition"] == expected_disposition
    assert isinstance(response, StreamingHttpResponse)
    body = b"".join(response.streaming_content)
    assert body.startswith("\ufeff".encode())


def test_no_export_columns_is_404(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")
    child_path = f"stubs/{stub.pk}/__tabs/children"

    with pytest.raises(Http404):
        fetch(child_path, data={"children-export": "csv"})


def test_unknown_export_format_is_404(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    with pytest.raises(Http404):
        fetch(_panel_path(stub.pk), data={"stub-export": "xlsx"})


def test_export_stays_scoped_when_site_thread_local_cleared(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(3)]

    response = fetch(_panel_path(stubs[0].pk), data={"stub-export": "csv"})
    drop_ambient_request()

    _header, *body = _rows(response)
    names = [row[0] for row in body]
    assert names == sorted(stub.name for stub in stubs)


def test_export_link_of_a_stacked_table_serves_its_csv(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-x", kind="a")
    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()
    document = lxml.html.fromstring(html)
    links = [
        a
        for a in document.cssselect("#a-table a")
        if a.text_content().strip() == "Export CSV"
    ]
    assert len({a.get("href") for a in links}) == 1
    assert all("btn-sm" in a.get("class").split() for a in links)
    assert all(a.cssselect("svg[data-icon='download']") for a in links)
    href = links[0].get("href").removeprefix("/test-panel/framework/")
    path_string, _, query = href.partition("?")

    response = fetch(path_string, data=dict(QueryDict(query).items()))

    header, *_body = _rows(response)
    assert header == ["Name", "Kind"]


@pytest.mark.django_db
def test_a_sort_keeps_the_default_ordering_behind_it_and_ends_on_pk(
    mock_site_context: Site,
) -> None:
    """Rows sharing a sort value would otherwise shuffle between pages."""

    class ScoreSortableTable(StubDataTable):
        @staticmethod
        def get_columns() -> list[Column]:
            return [
                Column(
                    header="SAT score",
                    template_name="cotton/data-table-cells/text.html",
                    attr="sat_score",
                    sortable=True,
                )
            ]

    request = RequestFactory().get("/", {"stub-sort": "-sat_score"})
    query = ScoreSortableTable.parse_query(request, "stub")

    rows = ScoreSortableTable.filter_queryset(
        request, ScoreSortableTable.get_queryset(request), query
    )

    assert rows.query.order_by == ("-sat_score", "name", "pk")


@pytest.mark.django_db
def test_a_sort_on_the_default_field_does_not_repeat_it(
    mock_site_context: Site,
) -> None:
    request = RequestFactory().get("/", {"stub-sort": "-name"})
    query = StubDataTable.parse_query(request, "stub")

    rows = StubDataTable.filter_queryset(
        request, StubDataTable.get_queryset(request), query
    )

    assert rows.query.order_by == ("-name", "pk")


# A table that names its default sort column shows that column as sorted
# before any sort is in the URL, so its first click flips the direction
# instead of repeating the order already on screen.


class _DefaultSortedDataTable(StubDataTable):
    default_sort = "name"

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            *StubDataTable.get_columns(),
            Column(
                header="SAT score",
                template_name="cotton/data-table-cells/text.html",
                attr="sat_score",
                sortable=True,
            ),
        ]


class _DefaultSortedTablePanel(DataTablePanel):
    title = "Default sorted"
    data_table = _DefaultSortedDataTable
    table_key = "defsort"


def _header_states(html: str) -> dict[str, str]:
    """Each sortable header's text mapped to the sort its link applies."""
    document = lxml.html.fromstring(html)
    return {
        link.text_content().strip(): link.get("href")
        for link in document.cssselect("thead a[href]")
    }


def test_the_default_sort_counts_as_the_effective_sort_but_not_as_a_parameter() -> None:
    request = RequestFactory().get("/")

    query = _DefaultSortedDataTable.parse_query(request, "defsort")

    assert query.effective_sort == "name"
    assert query.sort == ""
    assert "defsort-sort" not in query.to_params()


def test_with_no_sort_the_default_column_links_to_descending(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-x")
    panel = _bind_table_panel(_DefaultSortedTablePanel)

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    assert "defsort-sort=-name" in _header_states(html)["Name"]


def test_with_no_sort_another_column_still_links_to_ascending(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-x")
    panel = _bind_table_panel(_DefaultSortedTablePanel)

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    assert "defsort-sort=sat_score" in _header_states(html)["SAT score"]


def test_with_no_sort_the_default_column_reads_as_sorted(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-x")
    panel = _bind_table_panel(_DefaultSortedTablePanel)

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    document = lxml.html.fromstring(html)
    (sorted_header,) = document.cssselect("th[aria-sort='ascending']")
    assert "Name" in sorted_header.text_content()
    assert "Sorted by" not in html


def test_an_explicit_descending_sort_on_the_default_column_links_back_to_ascending(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-x")
    panel = _DefaultSortedTablePanel(
        PanelContext(
            request=RequestFactory().get("/p", {"defsort-sort": "-name"}),
            instance=None,
            base_url="/p",
            name="",
            config=SectionConfigBase,
            page_url="/p",
        )
    )

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    assert "defsort-sort=name" in _header_states(html)["Name"]


class _DefaultedFilterTable(StubDataTable):
    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [
            ChoiceFilter(
                "kind",
                "Kind",
                lookup="kind",
                choices=[("a", "A"), ("b", "B")],
                default=("a",),
            )
        ]


def test_a_filters_default_applies_when_its_parameter_is_absent() -> None:
    request = RequestFactory().get("/")

    query = _DefaultedFilterTable.parse_query(request, "stub")

    assert query.filters == {"kind": ["a"]}


def test_a_filters_default_does_not_apply_when_its_parameter_is_present() -> None:
    request = RequestFactory().get("/", {"stub-kind": "b"})

    query = _DefaultedFilterTable.parse_query(request, "stub")

    assert query.filters == {"kind": ["b"]}


def test_a_filters_default_applies_when_its_parameter_is_empty() -> None:
    request = RequestFactory().get("/", {"stub-kind": ""})

    query = _DefaultedFilterTable.parse_query(request, "stub")

    assert query.filters == {"kind": ["a"]}


def test_a_filters_default_applies_when_none_of_its_values_are_valid() -> None:
    request = RequestFactory().get("/", {"stub-kind": "zzz"})

    query = _DefaultedFilterTable.parse_query(request, "stub")

    assert query.filters == {"kind": ["a"]}


def test_removing_a_defaulted_filter_drops_its_parameter() -> None:
    request = RequestFactory().get("/", {"stub-kind": "b"})
    query = _DefaultedFilterTable.parse_query(request, "stub")

    assert query.filter_changes("kind", [])["stub-kind"] is None
    assert query.clear_filters_changes(["kind"])["stub-kind"] is None


class _DefaultedFilterTablePanel(DataTablePanel):
    title = "Defaulted"
    data_table = _DefaultedFilterTable
    table_key = "stub"


def _render_defaulted_filter_table(
    data: dict[str, str],
    panel_class: type[DataTablePanel] = _DefaultedFilterTablePanel,
) -> lxml.html.HtmlElement:
    panel = panel_class(
        PanelContext(
            request=RequestFactory().get("/p", data),
            instance=None,
            base_url="/p",
            name="",
            config=SectionConfigBase,
            page_url="/p",
        )
    )
    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )
    return lxml.html.fromstring(html)


@pytest.mark.django_db
def test_a_defaulted_filters_chip_has_no_remove_control(
    mock_site_context: Site,
) -> None:
    document = _render_defaulted_filter_table({"stub-kind": "b"})

    assert document.xpath(".//*[contains(normalize-space(), 'Kind: B')]")
    assert not document.cssselect('a[aria-label="Remove Kind filter"]')


@pytest.mark.django_db
def test_clear_all_is_hidden_while_a_defaulted_filter_is_at_its_default(
    mock_site_context: Site,
) -> None:
    document = _render_defaulted_filter_table({})

    assert not document.xpath(".//a[normalize-space()='Clear all']")


@pytest.mark.django_db
def test_clear_all_shows_once_a_defaulted_filter_leaves_its_default(
    mock_site_context: Site,
) -> None:
    document = _render_defaulted_filter_table({"stub-kind": "b"})

    (clear_link,) = document.xpath(".//a[normalize-space()='Clear all']")
    assert "stub-kind" not in clear_link.get("href")


class _NoChoicesFilterTable(StubDataTable):
    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [
            ChoiceFilter(
                "kind",
                "Kind",
                lookup="kind",
                choices=[],
                default=("a",),
                always_shown=True,
            )
        ]


class _NoChoicesFilterTablePanel(DataTablePanel):
    title = "No choices"
    data_table = _NoChoicesFilterTable
    table_key = "stub"


@pytest.mark.django_db
def test_a_filter_with_no_choices_is_offered_nowhere(
    mock_site_context: Site,
) -> None:
    document = _render_defaulted_filter_table({}, _NoChoicesFilterTablePanel)

    text = " ".join(document.text_content().split())
    assert "Kind:" not in text
    assert "Add filter" not in text
    assert "Clear all" not in text


class _NarrowCardsTable(StubDataTable):
    cards_when_narrow = True


class _NarrowCardsTablePanel(DataTablePanel):
    title = "Narrow cards"
    data_table = _NarrowCardsTable
    table_key = "stub"


def _table_and_card_classes(
    document: lxml.html.HtmlElement,
) -> tuple[set[str], set[str], set[str]]:
    """The classes on the wrapper around the table and its cards, on the
    table region and on the card list."""
    (wrapper,) = document.cssselect("[data-table-layout]")
    (region,) = wrapper.cssselect("[role='region']")
    (cards,) = wrapper.xpath("./ul")
    return (
        set(wrapper.get("class", "").split()),
        set(region.get("class", "").split()),
        set(cards.get("class", "").split()),
    )


@pytest.mark.django_db
def test_a_table_switches_to_cards_by_the_viewport_by_default(
    mock_site_context: Site,
) -> None:
    document = _render_defaulted_filter_table({}, _DefaultedFilterTablePanel)

    wrapper, region, cards = _table_and_card_classes(document)

    assert "@container" not in wrapper
    assert {"hidden", "md:block"} <= region
    assert "md:hidden" in cards


@pytest.mark.django_db
def test_a_cards_when_narrow_table_switches_by_its_own_containers_width(
    mock_site_context: Site,
) -> None:
    document = _render_defaulted_filter_table({}, _NarrowCardsTablePanel)

    wrapper, region, cards = _table_and_card_classes(document)

    assert "@container" in wrapper
    assert {"hidden", "@min-[58rem]:block"} <= region
    assert "md:block" not in region
    assert "@min-[58rem]:hidden" in cards
    assert "md:hidden" not in cards


class _NarrowCardsBulkTablePanel(_NarrowCardsTablePanel):
    def get_bulk_actions(self) -> list[BulkAction]:
        return [StubBulkAction()]


@pytest.mark.django_db
def test_a_cards_when_narrow_tables_card_select_all_sits_in_the_container_it_switches_on(
    mock_site_context: Site,
) -> None:
    document = _render_defaulted_filter_table({}, _NarrowCardsBulkTablePanel)

    (label,) = document.xpath("//label[contains(., 'Select all on this page')]")
    assert label.xpath("ancestor::*[@data-table-layout]")


def test_show_all_changes_selects_every_choice_of_each_defaulted_filter() -> None:
    request = RequestFactory().get("/", {"stub-page": "3"})
    query = _DefaultedFilterTable.parse_query(request, "stub")

    assert query.show_all_changes(_DefaultedFilterTable.get_filters()) == {
        "stub-kind": ["a", "b"],
        "stub-page": None,
    }


@pytest.mark.django_db
def test_an_empty_page_under_a_default_filter_offers_to_show_every_row(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-b", kind="b")

    document = _render_defaulted_filter_table({})

    (href,) = {
        link.get("href")
        for link in document.xpath(".//a[normalize-space()='Show all stub models']")
    }
    assert "stub-kind=a" in href
    assert "stub-kind=b" in href
    assert not document.xpath(".//*[contains(normalize-space(), 'Nothing to see')]")


@pytest.mark.django_db
def test_an_empty_table_under_a_default_filter_is_still_first_use(
    mock_site_context: Site,
) -> None:
    document = _render_defaulted_filter_table({})

    assert document.xpath(".//*[contains(normalize-space(), 'Nothing to see')]")
    assert not document.xpath(".//a[starts-with(normalize-space(), 'Show all')]")


def test_removing_a_filter_without_a_default_drops_its_parameter() -> None:
    request = RequestFactory().get("/", {"stub-kind": "a"})
    query = StubDataTable.parse_query(request, "stub")

    assert query.filter_changes("kind", [])["stub-kind"] is None
    assert query.clear_filters_changes(["kind"])["stub-kind"] is None


class _EmptyStateDataTable(StubDataTable):
    empty_state_template_name = "panel_framework/test_empty_state.html"


class _EmptyStateTablePanel(DataTablePanel):
    title = "Empty state"
    data_table = _EmptyStateDataTable
    table_key = "emptystate"


def _render_empty_state_table() -> lxml.html.HtmlElement:
    panel = _bind_table_panel(_EmptyStateTablePanel)
    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )
    return lxml.html.fromstring(html)


def test_an_empty_state_template_replaces_the_fixed_text_in_the_table(
    mock_site_context: Site,
) -> None:
    document = _render_empty_state_table()

    (cell,) = document.cssselect("table tbody td")
    assert cell.text_content().strip() == "Nothing here yet in emptystate-table."


def test_an_empty_state_template_replaces_the_fixed_text_in_the_cards(
    mock_site_context: Site,
) -> None:
    document = _render_empty_state_table()

    (card,) = document.cssselect("ul li")
    assert card.text_content().strip() == "Nothing here yet in emptystate-table."


def test_an_empty_state_template_is_not_rendered_on_a_page_with_rows(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a")

    document = _render_empty_state_table()

    assert document.cssselect(".stub-empty-state") == []


def test_a_table_without_an_empty_state_template_keeps_the_fixed_text(
    mock_site_context: Site,
) -> None:
    panel = _bind_table_panel(StubDataTablePanel)

    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )

    assert "Nothing to see" in html


def _rendered_table(data: dict[str, str] | None = None) -> lxml.html.HtmlElement:
    stub = make_stub(name="row-x")
    html = fetch(_panel_path(stub.pk), data=data or {}).content.decode()
    (table,) = lxml.html.fromstring(html).cssselect("#stub-table table")
    return table


def test_every_header_cell_has_column_scope(mock_site_context: Site) -> None:
    table = _rendered_table()

    headers = table.cssselect("thead th")
    assert headers
    assert all(th.get("scope") == "col" for th in headers)


def test_aria_sort_is_set_on_the_sorted_column_only(mock_site_context: Site) -> None:
    table = _rendered_table({"stub-sort": "-name"})

    sortable = [th for th in table.cssselect("thead th") if th.cssselect("a")]
    sorted_states = {th.text_content().strip(): th.get("aria-sort") for th in sortable}
    assert sorted_states["Name"] == "descending"
    assert [s for name, s in sorted_states.items() if name != "Name"] == ["none"] * (
        len(sortable) - 1
    )


def test_a_sort_links_text_is_its_column_header(mock_site_context: Site) -> None:
    table = _rendered_table()

    (name_link,) = [
        a for a in table.cssselect("thead th a") if a.text_content().strip() == "Name"
    ]
    icons = name_link.cssselect("svg")
    assert icons
    assert all(icon.xpath("ancestor::*[@aria-hidden='true']") for icon in icons)


def test_the_table_scrolls_in_a_labelled_focusable_region(
    mock_site_context: Site,
) -> None:
    table = _rendered_table()

    region = table.getparent()
    assert region.get("role") == "region"
    assert region.get("tabindex") == "0"
    assert region.get("aria-label")


def test_the_table_has_a_caption(mock_site_context: Site) -> None:
    table = _rendered_table()

    (caption,) = table.cssselect("caption")
    assert caption.text_content().strip()
    assert table.get("aria-labelledby") == caption.get("id")


class _NamedTablePanel(StubDataTablePanel):
    data_table = type("NamedStubDataTable", (StubDataTable,), {"noun": "widgets"})


def test_a_tables_noun_names_its_caption_and_region(mock_site_context: Site) -> None:
    assert _bind_table_panel(_NamedTablePanel).get_context_data()["noun"] == "widgets"


def test_a_table_without_a_noun_is_named_after_its_model(
    mock_site_context: Site,
) -> None:
    context = _bind_table_panel(StubDataTablePanel).get_context_data()

    assert (
        context["noun"]
        == StubDataTable.get_queryset(
            RequestFactory().get("/p")
        ).model._meta.verbose_name_plural
    )


def test_get_context_marks_each_row_with_the_has_row_detail_predicate(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")
    make_stub(name="row-b", kind="b")
    panel = _bind_table_panel(StubDataTablePanel)
    query, queryset = panel.narrow(panel.request)

    context = StubDetailDataTable.get_context(
        panel.request,
        query,
        queryset.order_by("name"),
        base_url="/p",
        page_url="/p",
        region_id="r",
    )

    rows = context["rows"]
    assert isinstance(rows, list)
    assert [(row["object"].name, row["has_row_detail"]) for row in rows] == [
        ("row-a", True),
        ("row-b", False),
    ]
    assert (
        context["row_detail_template_name"]
        == StubDetailDataTable.row_detail_template_name
    )


def test_get_context_has_no_row_detail_for_a_plain_table(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")
    panel = _bind_table_panel(StubDataTablePanel)
    query, queryset = panel.narrow(panel.request)

    context = StubPlainDataTable.get_context(
        panel.request,
        query,
        queryset,
        base_url="/p",
        page_url="/p",
        region_id="r",
    )

    rows = context["rows"]
    assert isinstance(rows, list)
    assert [row["has_row_detail"] for row in rows] == [False]
    assert context["row_detail_template_name"] is None


class _OverriddenExportPanel(StubDataTablePanel):
    """Exports only "keep" rows, whatever the screen shows, and records each
    `before_export` call with the names it was handed."""

    calls: list[list[str]] = []

    def get_export_queryset(self, request: HttpRequest) -> QuerySet:
        return self.get_queryset(request).filter(name__startswith="keep")

    def before_export(self, request: HttpRequest, rows: QuerySet) -> QuerySet:
        type(self).calls.append([row.name for row in rows])
        return rows.exclude(name__endswith="-dropped")


class _OverriddenExportPanelConfig(BaseViewConfig):
    url_name = "export-panel"
    menu_label = "Export panel"
    panel = _OverriddenExportPanel


def _fetch_from(
    config: SectionConfig, path: str, data: dict[str, str]
) -> HttpResponse | StreamingHttpResponse:
    return call_view(
        make_request(path, data=data), path, config=[NavGroup("Test", [config])]
    )


def test_an_overridden_export_queryset_still_honours_search_filters_and_sort(
    mock_site_context: Site,
) -> None:
    make_stub(name="keep-a", kind="a")
    make_stub(name="keep-c", kind="b")
    make_stub(name="keep-b", kind="b")
    make_stub(name="other-b", kind="b")
    make_stub(name="keep-nomatch", kind="a")

    response = _fetch_from(
        _OverriddenExportPanelConfig,
        "export-panel",
        {
            "stub-q": "keep-",
            "stub-kind": "b",
            "stub-sort": "-name",
            "stub-export": "csv",
        },
    )

    _header, *body = _rows(response)
    assert [row[0] for row in body] == ["keep-c", "keep-b"]


def test_before_export_runs_before_streaming_and_its_rows_are_streamed(
    mock_site_context: Site,
) -> None:
    make_stub(name="keep-1")
    make_stub(name="keep-2-dropped")
    _OverriddenExportPanel.calls = []

    response = _fetch_from(
        _OverriddenExportPanelConfig, "export-panel", {"stub-export": "csv"}
    )

    assert _OverriddenExportPanel.calls == [["keep-1", "keep-2-dropped"]]
    _header, *body = _rows(response)
    assert [row[0] for row in body] == ["keep-1"]
    assert len(_OverriddenExportPanel.calls) == 1


class _OverriddenExportListConfig(ListViewConfig):
    url_name = "export-list"
    menu_label = "Export list"
    list_view = StubDataTable
    table_key = "stubs"
    before_export_calls: list[list[str]] = []

    @classmethod
    def get_export_queryset(cls, request: HttpRequest) -> QuerySet:
        return StubDataTable.get_queryset(request).filter(name__startswith="keep")

    @classmethod
    def before_export(cls, request: HttpRequest, rows: QuerySet) -> QuerySet:
        cls.before_export_calls.append([row.name for row in rows])
        return rows

    @classmethod
    def get_export_scope_slug(cls, request: HttpRequest) -> str:
        return "Acme Org"


def test_a_list_config_overrides_reach_the_export(mock_site_context: Site) -> None:
    make_stub(name="keep-1")
    make_stub(name="skip-1")
    _OverriddenExportListConfig.before_export_calls = []

    response = _fetch_from(
        _OverriddenExportListConfig, "export-list", {"stubs-export": "csv"}
    )

    _header, *body = _rows(response)
    assert [row[0] for row in body] == ["keep-1"]
    assert _OverriddenExportListConfig.before_export_calls == [["keep-1"]]
    today = timezone.localdate().isoformat()
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="stubs-acme-org-{today}.csv"'
    )


def test_a_list_config_without_overrides_exports_the_lists_rows(
    mock_site_context: Site,
) -> None:
    class _PlainListConfig(ListViewConfig):
        url_name = "export-plain"
        menu_label = "Export plain"
        list_view = StubDataTable
        table_key = "stubs"

    make_stub(name="row-1")

    response = _fetch_from(_PlainListConfig, "export-plain", {"stubs-export": "csv"})

    _header, *body = _rows(response)
    assert [row[0] for row in body] == ["row-1"]
    today = timezone.localdate().isoformat()
    assert (
        response["Content-Disposition"] == f'attachment; filename="stubs-{today}.csv"'
    )


APPLIED_FILTER: list[str] = [
    'div [class="md:flex md:flex-wrap md:items-center md:gap-2 md:border-b md:border-border '
    'md:px-6 md:py-3 lg:min-h-16.75" x-bind:class="toolbarClass"]',
    'form [action="/test-panel/framework/stubs/N/__tabs/default" class="w-full px-4 pt-3 sm:px-6 '
    'md:w-auto md:min-w-40 md:max-w-72 md:flex-1 md:p-0 pb-0" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default" hx-swap="outerHTML" '
    'hx-sync="this:replace" hx-target="#stub-table" hx-trigger="submit, input changed delay:300ms '
    'from:#stub-q, search from:#stub-q" id="stub-search" method="get"]',
    'input [name="stub-sort" type="hidden" value="name"]',
    'input [name="stub-kind" type="hidden" value="a"]',
    "div []",
    'label [class="sr-only" for="stub-q"] Search',
    'div [class="relative"]',
    'span [aria-hidden="true" class="pointer-events-none absolute inset-y-0 left-0 flex '
    'items-center pl-3 text-muted"]',
    'svg [aria-hidden="true" class="inline size-4" data-icon="search" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m21 21l-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607" '
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="1.5"]',
    'input [class="pl-9 max-md:min-h-11" hx-preserve="" id="stub-q" name="stub-q" '
    'placeholder="Search..." type="search" value=""]',
    'div [class="hidden md:contents"]',
    'details [class="group relative shrink-0"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden"]',
    'span [class="cursor-pointer chip chip-secondary"] Kind: Alpha',
    'a [aria-label="Remove Kind filter" class="inline-flex text-current no-underline '
    'hover:text-primary" href="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" hx-swap="outerHTML" '
    'hx-target="#stub-table"]',
    'svg [aria-hidden="true" class="inline size-3" data-icon="close" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M6 18L18 6M6 6l12 12" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'svg [aria-hidden="true" class="inline size-3 transition-transform group-open:rotate-180" '
    'data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="mt-1 min-w-40 space-y-1 surface bg-surface absolute z-10 p-2"]',
    'a [class="flex items-center gap-2 whitespace-nowrap rounded-md px-2 py-1 text-on-surface '
    'no-underline hover:bg-surface-2" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" hx-swap="outerHTML" '
    'hx-target="#stub-table"]',
    'span [class="size-4 shrink-0"]',
    "text: Alpha",
    'svg [aria-hidden="true" class="inline size-4" data-icon="check" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m4.5 12.75l6 6l9-13.5" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'a [class="flex items-center gap-2 whitespace-nowrap rounded-md px-2 py-1 text-on-surface '
    'no-underline hover:bg-surface-2" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a&stub-kind=b&stub-sort=name" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a&stub-kind=b&stub-sort=name" '
    'hx-swap="outerHTML" hx-target="#stub-table"]',
    'span [class="size-4 shrink-0"]',
    "text: Beta",
    'details [class="group/add relative shrink-0"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden"]',
    'span [class="cursor-pointer chip chip-secondary"] Add filter',
    'svg [aria-hidden="true" class="inline size-3 transition-transform group-open/add:rotate-180" '
    'data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="surface bg-surface absolute z-10 mt-1 min-w-40 space-y-2 p-2"]',
    'details [class="group"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden flex '
    'cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-1 hover:bg-surface-2"] '
    "Active only",
    'svg [aria-hidden="true" class="inline size-3 text-muted transition-transform '
    'group-open:rotate-180" data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="mt-1 min-w-40 space-y-1 ps-2"]',
    'a [class="flex items-center gap-2 whitespace-nowrap rounded-md px-2 py-1 text-on-surface '
    'no-underline hover:bg-surface-2" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a&stub-sort=name&stub-active=1" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a&stub-sort=name&stub-active=1" '
    'hx-swap="outerHTML" hx-target="#stub-table"]',
    'span [class="size-4 shrink-0"]',
    "text: Active only",
    'a [class="btn btn-link btn-sm shrink-0 whitespace-nowrap" data-variant="link" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" hx-swap="outerHTML" '
    'hx-target="#stub-table"] Clear all',
    'a [class="btn btn-secondary btn-sm ml-auto shrink-0 whitespace-nowrap" '
    'data-variant="secondary" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a&stub-sort=name&stub-export=csv"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Export CSV",
    'svg [aria-hidden="true" class="inline size-5" data-icon="download" height="24" viewbox="0 0 '
    '24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12L12 '
    '16.5m0 0L7.5 12m4.5 4.5V3" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3 md:hidden" '
    'data-mobile-only="true" data-storage-key="stub-sheet" x-data="sidePanel"]',
    'span [class="chip chip-secondary"] Kind: Alpha',
    'a [aria-label="Remove Kind filter" class="inline-flex text-current no-underline '
    'hover:text-primary" href="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" hx-swap="outerHTML" '
    'hx-target="#stub-table"]',
    'svg [aria-hidden="true" class="inline size-3" data-icon="close" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M6 18L18 6M6 6l12 12" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="flex shrink-0 items-center gap-2"]',
    'button [class="btn btn-secondary btn-sm" data-variant="secondary" type="button" '
    'x-on:click="toggle"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Filter",
    'svg [aria-hidden="true" class="inline size-5" data-icon="filter" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M12 3c2.755 0 5.455.232 8.083.678c.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 '
    "1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 "
    "21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 "
    '5.818V4.774c0-.54.384-1.006.917-1.096A48.3 48.3 0 0 1 12 3" fill="none" '
    'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="relative inline-block" x-data="dropdownMenu"]',
    'button [aria-haspopup="menu" aria-label="Sort" class="group/menu btn btn-secondary btn-sm" '
    'type="button" x-bind:aria-expanded="open" x-on:click="toggle" '
    'x-on:keydown.arrow-down.prevent="openFromTrigger" '
    'x-on:keydown.arrow-up.prevent="openFromTrigger" x-ref="menuButton"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Sort",
    'svg [aria-hidden="true" class="inline size-5" data-icon="sort_neutral" height="24" '
    'viewbox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0l-3.75-3.75M17.25 21L21 17.25" '
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="1.5"]',
    'div [class="dropdown-panel fixed w-56 bg-surface border border-border rounded-md shadow-lg '
    'z-[9999]" style="display: none" x-cloak="" x-on:click.away="close" '
    'x-on:keydown.arrow-down.prevent="focusNextItem" '
    'x-on:keydown.arrow-up.prevent="focusPreviousItem" x-on:keydown.end.prevent="focusLastItem" '
    'x-on:keydown.escape.window.capture="onEscape" x-on:keydown.home.prevent="focusFirstItem" '
    'x-on:scroll.window="closeOnScroll" x-ref="menuPanel" x-show="open" '
    'x-transition:enter="transition ease-out duration-100" x-transition:enter-end="transform '
    'opacity-100 scale-100" x-transition:enter-start="transform opacity-0 scale-95" '
    'x-transition:leave="transition ease-in duration-75" x-transition:leave-end="transform '
    'opacity-0 scale-95" x-transition:leave-start="transform opacity-100 scale-100"]',
    'div [aria-label="Sort by" class="py-1 space-y-1" role="menu"]',
    'a [aria-current="true" class="block w-full text-left px-4 py-2 text-sm hover:bg-surface-2 '
    "transition-colors no-underline cursor-pointer flex min-h-11 items-center justify-between "
    'text-on-surface font-semibold text-muted" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a&stub-sort=-name" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a&stub-sort=-name" '
    'hx-swap="outerHTML" hx-target="#stub-table" role="menuitem"] Name',
    'span [aria-hidden="true"]',
    'svg [aria-hidden="true" class="inline size-5 ml-2" data-icon="sort_asc" height="24" '
    'viewbox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m4.5 15.75l7.5-7.5l7.5 7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'a [class="btn btn-secondary btn-sm" data-variant="secondary" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a&stub-sort=name&stub-export=csv"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Export CSV",
    'svg [aria-hidden="true" class="inline size-5" data-icon="download" height="24" viewbox="0 0 '
    '24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12L12 '
    '16.5m0 0L7.5 12m4.5 4.5V3" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'dialog [aria-label="Filter" class="side-panel-dialog modal-backdrop-host bg-transparent '
    'md:hidden" data-variant="bottom-sheet" id="stub-sheet" x-ref="panelDialog"]',
    'div [class="side-panel-body bg-surface bottom-sheet overflow-y-auto overscroll-contain"]',
    'form [action="/test-panel/framework/stubs/N/__tabs/default" class="flex flex-col gap-4 p-4" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default" hx-swap="outerHTML" '
    'hx-target="#stub-table" method="get"]',
    'div [class="flex items-center gap-1"]',
    'h2 [class="flex-1 min-w-0 text-lg font-semibold"] Filter',
    'a [class="btn btn-link btn-sm min-w-11" data-variant="link" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-sort=name" hx-swap="outerHTML" '
    'hx-target="#stub-table"] Reset',
    'button [aria-label="Close" class="-my-2 -me-3 flex size-11 shrink-0 cursor-pointer '
    "items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-2 "
    'hover:text-on-surface" type="button" x-on:click="requestClose"]',
    'svg [aria-hidden="true" class="inline size-5" data-icon="close" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M6 18L18 6M6 6l12 12" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'fieldset [class="space-y-2 border-0 p-0"]',
    'legend [class="px-0 text-xs font-semibold uppercase tracking-wide text-muted"] Kind',
    'div [class="flex flex-wrap gap-2"]',
    'label [class="relative inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-full '
    "border border-border px-3 py-1 text-sm has-[:checked]:border-primary "
    'has-[:checked]:bg-primary has-[:checked]:text-on-primary"]',
    'input [checked="checked" class="sr-only" name="stub-kind" type="checkbox" value="a"]',
    "text: Alpha",
    'label [class="relative inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-full '
    "border border-border px-3 py-1 text-sm has-[:checked]:border-primary "
    'has-[:checked]:bg-primary has-[:checked]:text-on-primary"]',
    'input [class="sr-only" name="stub-kind" type="checkbox" value="b"]',
    "text: Beta",
    'fieldset [class="space-y-2 border-0 p-0"]',
    'legend [class="px-0 text-xs font-semibold uppercase tracking-wide text-muted"] Active only',
    'div [class="flex flex-wrap gap-2"]',
    'label [class="relative inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-full '
    "border border-border px-3 py-1 text-sm has-[:checked]:border-primary "
    'has-[:checked]:bg-primary has-[:checked]:text-on-primary"]',
    'input [class="sr-only" name="stub-active" type="checkbox" value="1"]',
    "text: Active only",
    'footer [class="panel-surface sticky bottom-0 z-10 flex items-center justify-between gap-3 '
    'border-t border-border px-6 py-4 max-sm:flex-wrap mt-auto -mx-4 -mb-4"]',
    'div [class="shrink-0"]',
    'button [class="btn btn-secondary" data-variant="secondary" type="button" x-on:click="close"] '
    "Cancel",
    'div [class="flex min-w-0 flex-wrap items-center justify-end gap-3"]',
    'button [class="btn btn-primary" data-variant="primary" type="submit"] Show results',
    "style [] @media (scripting: none) { #stub-sheet { display: block; position: static; opacity: "
    "1; transform: none; } }",
]

NO_FILTER_APPLIED: list[str] = [
    'div [class="md:flex md:flex-wrap md:items-center md:gap-2 md:border-b md:border-border '
    'md:px-6 md:py-3 lg:min-h-16.75" x-bind:class="toolbarClass"]',
    'form [action="/test-panel/framework/stubs/N/__tabs/default" class="w-full px-4 pt-3 sm:px-6 '
    'md:w-auto md:min-w-40 md:max-w-72 md:flex-1 md:p-0 pb-0" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default" hx-swap="outerHTML" '
    'hx-sync="this:replace" hx-target="#stub-table" hx-trigger="submit, input changed delay:300ms '
    'from:#stub-q, search from:#stub-q" id="stub-search" method="get"]',
    "div []",
    'label [class="sr-only" for="stub-q"] Search',
    'div [class="relative"]',
    'span [aria-hidden="true" class="pointer-events-none absolute inset-y-0 left-0 flex '
    'items-center pl-3 text-muted"]',
    'svg [aria-hidden="true" class="inline size-4" data-icon="search" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m21 21l-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607" '
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="1.5"]',
    'input [class="pl-9 max-md:min-h-11" hx-preserve="" id="stub-q" name="stub-q" '
    'placeholder="Search..." type="search" value=""]',
    'div [class="hidden md:contents"]',
    'details [class="group relative shrink-0"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden"]',
    'span [class="cursor-pointer chip chip-secondary"] Kind',
    'svg [aria-hidden="true" class="inline size-3 transition-transform group-open:rotate-180" '
    'data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="mt-1 min-w-40 space-y-1 surface bg-surface absolute z-10 p-2"]',
    'a [class="flex items-center gap-2 whitespace-nowrap rounded-md px-2 py-1 text-on-surface '
    'no-underline hover:bg-surface-2" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-kind=a" hx-swap="outerHTML" '
    'hx-target="#stub-table"]',
    'span [class="size-4 shrink-0"]',
    "text: Alpha",
    'a [class="flex items-center gap-2 whitespace-nowrap rounded-md px-2 py-1 text-on-surface '
    'no-underline hover:bg-surface-2" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-kind=b" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-kind=b" hx-swap="outerHTML" '
    'hx-target="#stub-table"]',
    'span [class="size-4 shrink-0"]',
    "text: Beta",
    'details [class="group/add relative shrink-0"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden"]',
    'span [class="cursor-pointer chip chip-secondary"] Add filter',
    'svg [aria-hidden="true" class="inline size-3 transition-transform group-open/add:rotate-180" '
    'data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="surface bg-surface absolute z-10 mt-1 min-w-40 space-y-2 p-2"]',
    'details [class="group"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden flex '
    'cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-1 hover:bg-surface-2"] '
    "Active only",
    'svg [aria-hidden="true" class="inline size-3 text-muted transition-transform '
    'group-open:rotate-180" data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="mt-1 min-w-40 space-y-1 ps-2"]',
    'a [class="flex items-center gap-2 whitespace-nowrap rounded-md px-2 py-1 text-on-surface '
    'no-underline hover:bg-surface-2" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-active=1" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-active=1" hx-swap="outerHTML" '
    'hx-target="#stub-table"]',
    'span [class="size-4 shrink-0"]',
    "text: Active only",
    'a [class="btn btn-secondary btn-sm ml-auto shrink-0 whitespace-nowrap" '
    'data-variant="secondary" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-export=csv"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Export CSV",
    'svg [aria-hidden="true" class="inline size-5" data-icon="download" height="24" viewbox="0 0 '
    '24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12L12 '
    '16.5m0 0L7.5 12m4.5 4.5V3" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3 md:hidden" '
    'data-mobile-only="true" data-storage-key="stub-sheet" x-data="sidePanel"]',
    'div [class="flex shrink-0 items-center gap-2"]',
    'button [class="btn btn-secondary btn-sm" data-variant="secondary" type="button" '
    'x-on:click="toggle"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Filter",
    'svg [aria-hidden="true" class="inline size-5" data-icon="filter" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M12 3c2.755 0 5.455.232 8.083.678c.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 '
    "1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 "
    "21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 "
    '5.818V4.774c0-.54.384-1.006.917-1.096A48.3 48.3 0 0 1 12 3" fill="none" '
    'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="relative inline-block" x-data="dropdownMenu"]',
    'button [aria-haspopup="menu" aria-label="Sort" class="group/menu btn btn-secondary btn-sm" '
    'type="button" x-bind:aria-expanded="open" x-on:click="toggle" '
    'x-on:keydown.arrow-down.prevent="openFromTrigger" '
    'x-on:keydown.arrow-up.prevent="openFromTrigger" x-ref="menuButton"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Sort",
    'svg [aria-hidden="true" class="inline size-5" data-icon="sort_neutral" height="24" '
    'viewbox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0l-3.75-3.75M17.25 21L21 17.25" '
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="1.5"]',
    'div [class="dropdown-panel fixed w-56 bg-surface border border-border rounded-md shadow-lg '
    'z-[9999]" style="display: none" x-cloak="" x-on:click.away="close" '
    'x-on:keydown.arrow-down.prevent="focusNextItem" '
    'x-on:keydown.arrow-up.prevent="focusPreviousItem" x-on:keydown.end.prevent="focusLastItem" '
    'x-on:keydown.escape.window.capture="onEscape" x-on:keydown.home.prevent="focusFirstItem" '
    'x-on:scroll.window="closeOnScroll" x-ref="menuPanel" x-show="open" '
    'x-transition:enter="transition ease-out duration-100" x-transition:enter-end="transform '
    'opacity-100 scale-100" x-transition:enter-start="transform opacity-0 scale-95" '
    'x-transition:leave="transition ease-in duration-75" x-transition:leave-end="transform '
    'opacity-0 scale-95" x-transition:leave-start="transform opacity-100 scale-100"]',
    'div [aria-label="Sort by" class="py-1 space-y-1" role="menu"]',
    'a [aria-current="true" class="block w-full text-left px-4 py-2 text-sm hover:bg-surface-2 '
    "transition-colors no-underline cursor-pointer flex min-h-11 items-center justify-between "
    'text-on-surface font-semibold text-muted" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-sort=-name" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?stub-sort=-name" hx-swap="outerHTML" '
    'hx-target="#stub-table" role="menuitem"] Name',
    'span [aria-hidden="true"]',
    'svg [aria-hidden="true" class="inline size-5 ml-2" data-icon="sort_asc" height="24" '
    'viewbox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m4.5 15.75l7.5-7.5l7.5 7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'a [class="btn btn-secondary btn-sm" data-variant="secondary" '
    'href="/test-panel/framework/stubs/N/__tabs/default?stub-export=csv"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Export CSV",
    'svg [aria-hidden="true" class="inline size-5" data-icon="download" height="24" viewbox="0 0 '
    '24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12L12 '
    '16.5m0 0L7.5 12m4.5 4.5V3" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'dialog [aria-label="Filter" class="side-panel-dialog modal-backdrop-host bg-transparent '
    'md:hidden" data-variant="bottom-sheet" id="stub-sheet" x-ref="panelDialog"]',
    'div [class="side-panel-body bg-surface bottom-sheet overflow-y-auto overscroll-contain"]',
    'form [action="/test-panel/framework/stubs/N/__tabs/default" class="flex flex-col gap-4 p-4" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default" hx-swap="outerHTML" '
    'hx-target="#stub-table" method="get"]',
    'div [class="flex items-center gap-1"]',
    'h2 [class="flex-1 min-w-0 text-lg font-semibold"] Filter',
    'a [class="btn btn-link btn-sm min-w-11" data-variant="link" '
    'href="/test-panel/framework/stubs/N/__tabs/default?" '
    'hx-get="/test-panel/framework/stubs/N/__tabs/default?" hx-swap="outerHTML" '
    'hx-target="#stub-table"] Reset',
    'button [aria-label="Close" class="-my-2 -me-3 flex size-11 shrink-0 cursor-pointer '
    "items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-2 "
    'hover:text-on-surface" type="button" x-on:click="requestClose"]',
    'svg [aria-hidden="true" class="inline size-5" data-icon="close" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M6 18L18 6M6 6l12 12" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'fieldset [class="space-y-2 border-0 p-0"]',
    'legend [class="px-0 text-xs font-semibold uppercase tracking-wide text-muted"] Kind',
    'div [class="flex flex-wrap gap-2"]',
    'label [class="relative inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-full '
    "border border-border px-3 py-1 text-sm has-[:checked]:border-primary "
    'has-[:checked]:bg-primary has-[:checked]:text-on-primary"]',
    'input [class="sr-only" name="stub-kind" type="checkbox" value="a"]',
    "text: Alpha",
    'label [class="relative inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-full '
    "border border-border px-3 py-1 text-sm has-[:checked]:border-primary "
    'has-[:checked]:bg-primary has-[:checked]:text-on-primary"]',
    'input [class="sr-only" name="stub-kind" type="checkbox" value="b"]',
    "text: Beta",
    'fieldset [class="space-y-2 border-0 p-0"]',
    'legend [class="px-0 text-xs font-semibold uppercase tracking-wide text-muted"] Active only',
    'div [class="flex flex-wrap gap-2"]',
    'label [class="relative inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-full '
    "border border-border px-3 py-1 text-sm has-[:checked]:border-primary "
    'has-[:checked]:bg-primary has-[:checked]:text-on-primary"]',
    'input [class="sr-only" name="stub-active" type="checkbox" value="1"]',
    "text: Active only",
    'footer [class="panel-surface sticky bottom-0 z-10 flex items-center justify-between gap-3 '
    'border-t border-border px-6 py-4 max-sm:flex-wrap mt-auto -mx-4 -mb-4"]',
    'div [class="shrink-0"]',
    'button [class="btn btn-secondary" data-variant="secondary" type="button" x-on:click="close"] '
    "Cancel",
    'div [class="flex min-w-0 flex-wrap items-center justify-end gap-3"]',
    'button [class="btn btn-primary" data-variant="primary" type="submit"] Show results',
    "style [] @media (scripting: none) { #stub-sheet { display: block; position: static; opacity: "
    "1; transform: none; } }",
]


def _normalised_toolbar(html: str) -> list[str]:
    """One entry per element of the toolbar, and per run of text after one: tag,
    sorted attributes and the element's own text, with row ids made constant."""
    document = lxml.html.fromstring(html)
    (search_form,) = document.cssselect("form#stub-search")
    toolbar = search_form.getparent()
    entries: list[str] = []
    for element in toolbar.iter():
        if not isinstance(element.tag, str):
            continue
        attributes = " ".join(
            f'{name}="{" ".join(value.split())}"'
            for name, value in sorted(element.attrib.items())
        )
        text = re.sub(r"\s+", " ", element.text or "").strip()
        entries.append(f"{element.tag} [{attributes}] {text}".strip())
        tail = re.sub(r"\s+", " ", element.tail or "").strip()
        if tail and element is not toolbar:
            entries.append(f"text: {tail}")
    return [re.sub(r"stubs/\d+/", "stubs/N/", entry) for entry in entries]


def _toolbar_for(query: dict[str, str]) -> list[str]:
    stub = make_stub(name="row-x", kind="a")
    html = fetch(f"stubs/{stub.pk}/__tabs/default", data=query).content.decode()
    return _normalised_toolbar(html)


def test_the_toolbar_with_a_filter_applied_renders_the_same_controls_in_order(
    mock_site_context: Site,
) -> None:
    assert _toolbar_for({"stub-kind": "a", "stub-sort": "name"}) == APPLIED_FILTER


def test_the_toolbar_with_no_filter_applied_renders_the_same_controls_in_order(
    mock_site_context: Site,
) -> None:
    assert _toolbar_for({}) == NO_FILTER_APPLIED
