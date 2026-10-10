"""Tests for data tables: query parsing, columns, region refreshes, filters, the
mobile card layout and the CSV export."""

from __future__ import annotations

import csv
import io

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.http import Http404, HttpResponse, QueryDict, StreamingHttpResponse
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.utils import timezone

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.filters import TableFilter
from freedom_ls.panel_framework.panels import DataTablePanel
from freedom_ls.panel_framework.tables import Column, DataTable, ExportColumn
from freedom_ls.panel_framework.views import SectionConfigBase
from freedom_ls.tests.site_context import drop_ambient_request

from .helpers import make_stub
from .stub_panels import StubDataTable, StubDataTablePanel
from .view_helpers import fetch

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
        template="cotton/data-table-cells/link.html",
        text_attr="name",
        url_name="panel_framework_test:framework",
        url_path_template="stubs/{pk}",
    )

    assert column.is_link is True


def test_a_column_with_no_url_is_not_a_link() -> None:
    column = Column(
        header="Name", template="cotton/data-table-cells/text.html", attr="name"
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
        if "a-sort=name" in link.get("href", "")
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
    assert f"Showing 1\u2013{_PAGE_SIZE} of {_ROWS}" in html
    assert ", sorted by" not in html


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
    assert "Sort" in [legend.text_content().strip() for legend in legends]
    assert sheet.xpath(".//button[@type='button'][normalize-space()='Cancel']")
    assert sheet.xpath(".//button[@type='submit'][normalize-space()='Show results']")


def test_sheet_without_declared_filters_renders_no_filter_fieldset(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-00")

    html = fetch(f"stubs/{stub.pk}/__tabs/sortonly").content.decode()

    document = lxml.html.fromstring(html)
    (sheet,) = document.cssselect("dialog#sortonly-sheet")
    legends = [legend.text_content().strip() for legend in sheet.cssselect("legend")]
    assert legends == ["Sort"]
    assert not sheet.cssselect("select")


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
    (link,) = [
        a for a in document.cssselect("#a-table a") if a.text_content() == "Export CSV"
    ]
    href = link.get("href").removeprefix("/test-panel/framework/")
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
                    template="cotton/data-table-cells/text.html",
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
