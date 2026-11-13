"""Tests for the toolbar family: <c-panel-toolbar />, <c-panel-search-field />,
<c-panel-filter-toggle /> and <c-panel-applied-filter />."""

from __future__ import annotations

import re

import lxml.html

from ..cotton_helpers import render_cotton


def test_search_field_label_for_matches_input_id() -> None:
    html = render_cotton('<c-panel-search-field name="q" label="Search learners" />')

    label_match = re.search(r'<label for="([^"]+)"', html)
    input_match = re.search(r'<input[^>]*\bid="([^"]+)"', html)

    assert label_match is not None
    assert input_match is not None
    assert label_match.group(1) == input_match.group(1)


def test_search_field_default_id_derives_from_name() -> None:
    html = render_cotton('<c-panel-search-field name="q" label="Search learners" />')

    assert 'id="search-q"' in html


def test_search_field_label_text_is_visible() -> None:
    html = render_cotton('<c-panel-search-field name="q" label="Search learners" />')

    assert "Search learners" in html


def test_search_field_label_hidden_adds_sr_only() -> None:
    html = render_cotton(
        '<c-panel-search-field name="q" label="Search learners" label_hidden="true" />'
    )

    label_match = re.search(r'<label[^>]*class="([^"]*)"', html)

    assert label_match is not None
    assert "sr-only" in label_match.group(1)


def test_search_field_label_not_hidden_by_default() -> None:
    html = render_cotton('<c-panel-search-field name="q" label="Search learners" />')

    label_match = re.search(r'<label[^>]*class="([^"]*)"', html)

    assert label_match is not None
    assert "sr-only" not in label_match.group(1)


def test_search_field_icon_is_decorative() -> None:
    html = render_cotton('<c-panel-search-field name="q" label="Search learners" />')

    assert re.search(
        r'<span aria-hidden="true"[^>]*>\s*<svg[^>]*data-icon="search"', html
    )


def test_search_field_attrs_land_on_the_input() -> None:
    html = render_cotton(
        '<c-panel-search-field name="q" label="Search learners" hx-get="/search/" />'
    )

    input_start = html.index("<input")
    input_end = html.index(">", input_start)

    assert 'hx-get="/search/"' in html[input_start:input_end]


def test_search_field_label_hidden_false_string_keeps_the_label_visible() -> None:
    html = render_cotton(
        '<c-panel-search-field name="q" label="Search learners" label_hidden="False" />'
    )

    label_match = re.search(r'<label[^>]*class="([^"]*)"', html)

    assert label_match is not None
    assert "sr-only" not in label_match.group(1)


def _parse(html: str) -> lxml.html.HtmlElement:
    return lxml.html.fragment_fromstring(html, create_parent="div")


def test_toolbar_root_has_no_toolbar_role() -> None:
    html = render_cotton("<c-panel-toolbar />")

    assert 'role="toolbar"' not in html


def test_toolbar_row_layout_is_a_bordered_row_from_md() -> None:
    html = render_cotton("<c-panel-toolbar />")

    (root,) = _parse(html).xpath("./div")
    assert set(root.get("class").split()) >= {
        "md:flex",
        "md:border-b",
        "md:px-6",
        "md:py-3",
    }


def test_toolbar_reserve_layout_keeps_the_row_height_and_rule_from_lg() -> None:
    html = render_cotton('<c-panel-toolbar layout="reserve" />')

    (root,) = _parse(html).xpath("./div")
    assert set(root.get("class").split()) == {
        "lg:min-h-16.75",
        "lg:border-b",
        "lg:border-border",
    }


def test_toolbar_none_layout_has_no_classes() -> None:
    html = render_cotton('<c-panel-toolbar layout="none" />')

    (root,) = _parse(html).xpath("./div")
    assert root.get("class") == ""


def test_toolbar_bound_class_lands_on_the_root() -> None:
    html = render_cotton('<c-panel-toolbar bound_class="toolbarClass" />')

    (root,) = _parse(html).xpath("./div")
    assert root.get("x-bind:class") == "toolbarClass"


def test_toolbar_without_bound_class_has_no_class_binding() -> None:
    html = render_cotton("<c-panel-toolbar />")

    assert "x-bind:class" not in html


def test_toolbar_search_comes_before_the_desktop_controls() -> None:
    html = render_cotton(
        """
        <c-panel-toolbar>
            <c-slot name="search"><form id="s"></form></c-slot>
            <c-slot name="filters"><i id="f"></i></c-slot>
            <c-slot name="actions"><b id="a"></b></c-slot>
        </c-panel-toolbar>
        """
    )

    (root,) = _parse(html).xpath("./div")
    assert [child.get("id") for child in root.xpath("./form")] == ["s"]
    (desktop,) = root.xpath('./div[contains(@class, "md:contents")]')
    assert [child.get("id") for child in desktop] == ["f", "a"]
    assert "hidden" in desktop.get("class").split()


def test_toolbar_mobile_row_renders_only_with_content() -> None:
    html = render_cotton("<c-panel-toolbar />")

    assert "md:hidden" not in html


def test_toolbar_mobile_row_is_hidden_from_md() -> None:
    html = render_cotton(
        '<c-panel-toolbar><c-slot name="mobile"><i></i></c-slot></c-panel-toolbar>'
    )

    (mobile,) = _parse(html).xpath('.//div[contains(@class, "md:hidden")]')
    assert mobile.xpath("./i")


def test_toolbar_sheet_key_makes_the_mobile_row_a_side_panel() -> None:
    html = render_cotton(
        """
        <c-panel-toolbar sheet_key="t-sheet">
            <c-slot name="mobile"><i></i></c-slot>
        </c-panel-toolbar>
        """
    )

    (mobile,) = _parse(html).xpath('.//div[contains(@class, "md:hidden")]')
    assert mobile.get("x-data") == "sidePanel"
    assert mobile.get("data-storage-key") == "t-sheet"
    assert mobile.get("data-mobile-only") == "true"


def test_toolbar_mobile_row_is_plain_without_a_sheet_key() -> None:
    html = render_cotton(
        '<c-panel-toolbar><c-slot name="mobile"><i></i></c-slot></c-panel-toolbar>'
    )

    (mobile,) = _parse(html).xpath('.//div[contains(@class, "md:hidden")]')
    assert mobile.get("x-data") is None


def test_filter_toggle_is_a_closed_details_popover() -> None:
    html = render_cotton(
        '<c-panel-filter-toggle label="Kind"><p id="body"></p></c-panel-filter-toggle>'
    )

    (details,) = _parse(html).xpath("//details")
    assert details.get("open") is None
    (summary,) = details.xpath("./summary")
    assert "Kind" in summary.text_content()
    assert details.xpath('./p[@id="body"]')


def test_filter_toggle_summary_slot_replaces_the_label_chip() -> None:
    html = render_cotton(
        """
        <c-panel-filter-toggle label="Kind">
            <c-slot name="summary"><em>Kind: Alpha</em></c-slot>
        </c-panel-filter-toggle>
        """
    )

    (summary,) = _parse(html).xpath("//summary")
    assert summary.text_content().strip() == "Kind: Alpha"


def test_filter_toggle_add_variant_turns_its_chevron_with_its_own_group() -> None:
    html = render_cotton('<c-panel-filter-toggle variant="add" label="Add filter" />')

    (details,) = _parse(html).xpath("//details")
    assert "group/add" in details.get("class").split()
    assert "group-open/add:rotate-180" in html


def test_filter_toggle_nested_variant_is_a_row_summary() -> None:
    html = render_cotton('<c-panel-filter-toggle variant="nested" label="Active" />')

    (summary,) = _parse(html).xpath("//summary")
    assert "justify-between" in summary.get("class").split()
    assert summary.text_content().strip() == "Active"


def test_applied_filter_label_is_visible_text() -> None:
    html = render_cotton('<c-panel-applied-filter label="Status: Inactive" />')

    assert "Status: Inactive" in html


def test_applied_filter_without_remove_href_has_no_remove_control() -> None:
    html = render_cotton('<c-panel-applied-filter label="Status: Inactive" />')

    assert "<a " not in html
    assert "<button" not in html


def test_applied_filter_remove_is_a_link_that_works_without_javascript() -> None:
    html = render_cotton(
        '<c-panel-applied-filter label="Status: Inactive" remove_href="?q=1" />'
    )

    (link,) = _parse(html).xpath("//a")
    assert link.get("href") == "?q=1"


def test_applied_filter_remove_default_accessible_name() -> None:
    html = render_cotton(
        '<c-panel-applied-filter label="Status: Inactive" remove_href="?" />'
    )

    assert 'aria-label="Remove filter: Status: Inactive"' in html


def test_applied_filter_remove_label_overrides_the_accessible_name() -> None:
    html = render_cotton(
        '<c-panel-applied-filter label="Kind: Alpha" remove_href="?" '
        'remove_label="Remove Kind filter" />'
    )

    assert 'aria-label="Remove Kind filter"' in html


def test_applied_filter_attrs_land_on_the_remove_link() -> None:
    html = render_cotton(
        '<c-panel-applied-filter label="Status: Inactive" remove_href="?" '
        'hx-get="/filters/" />'
    )

    (link,) = _parse(html).xpath("//a")
    assert link.get("hx-get") == "/filters/"


def test_applied_filter_close_icon_is_decorative() -> None:
    html = render_cotton(
        '<c-panel-applied-filter label="Status: Inactive" remove_href="?" />'
    )

    assert re.search(r'<svg[^>]*aria-hidden="true"[^>]*data-icon="close"', html)


def test_applied_filter_disclosure_adds_a_chevron_and_pointer_cursor() -> None:
    html = render_cotton(
        '<c-panel-applied-filter label="Status: Inactive" disclosure="true" />'
    )

    assert 'data-icon="dropdown"' in html
    assert "cursor-pointer" in html


def test_applied_filter_without_disclosure_has_no_chevron() -> None:
    html = render_cotton('<c-panel-applied-filter label="Status: Inactive" />')

    assert 'data-icon="dropdown"' not in html


def test_applied_filter_disclosure_false_string_is_off() -> None:
    html = render_cotton(
        '<c-panel-applied-filter label="Status: Inactive" disclosure="False" />'
    )

    assert 'data-icon="dropdown"' not in html


def test_applied_filter_label_is_escaped() -> None:
    html = render_cotton('<c-panel-applied-filter label="<script>alert(1)</script>" />')

    assert "<script>alert(1)</script>" not in html
