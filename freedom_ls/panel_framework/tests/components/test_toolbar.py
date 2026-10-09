"""Tests for the toolbar family: <c-panel-toolbar />, <c-panel-search-field />,
<c-panel-filter-toggle /> and <c-panel-applied-filter />."""

from __future__ import annotations

import re

from ..cotton_helpers import render_cotton


def test_toolbar_root_has_no_toolbar_role() -> None:
    html = render_cotton("<c-panel-toolbar />")

    assert 'role="toolbar"' not in html


def test_toolbar_clear_all_renders_only_with_clear_all_href() -> None:
    html = render_cotton('<c-panel-toolbar clear_all_href="?clear=1" />')

    assert 'href="?clear=1"' in html
    assert "Clear all" in html


def test_toolbar_clear_all_absent_without_clear_all_href() -> None:
    html = render_cotton("<c-panel-toolbar />")

    assert "Clear all" not in html


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
        r'<span aria-hidden="true"[^>]*>\s*<svg[^>]*aria-label="search"', html
    )


def test_search_field_attrs_land_on_the_input() -> None:
    html = render_cotton(
        '<c-panel-search-field name="q" label="Search learners" hx-get="/search/" />'
    )

    input_start = html.index("<input")
    input_end = html.index(">", input_start)

    assert 'hx-get="/search/"' in html[input_start:input_end]


def test_filter_toggle_is_a_button_type_button() -> None:
    html = render_cotton('<c-panel-filter-toggle label="Inactive" />')

    assert '<button type="button"' in html


def test_filter_toggle_aria_pressed_true_when_pressed() -> None:
    html = render_cotton('<c-panel-filter-toggle label="Inactive" pressed="true" />')

    assert 'aria-pressed="true"' in html


def test_filter_toggle_aria_pressed_false_when_not_pressed() -> None:
    html = render_cotton('<c-panel-filter-toggle label="Inactive" />')

    assert 'aria-pressed="false"' in html


def test_filter_toggle_pressed_check_icon_is_decorative() -> None:
    html = render_cotton('<c-panel-filter-toggle label="Inactive" pressed="true" />')

    assert re.search(
        r'<span aria-hidden="true"[^>]*>\s*<svg[^>]*aria-label="check"', html
    )


def test_filter_toggle_unpressed_has_no_check_icon() -> None:
    html = render_cotton('<c-panel-filter-toggle label="Inactive" />')

    assert 'aria-label="check"' not in html


def test_applied_filter_remove_button_accessible_name() -> None:
    html = render_cotton('<c-panel-applied-filter label="Status: Inactive" />')

    assert 'aria-label="Remove filter: Status: Inactive"' in html


def test_applied_filter_label_is_visible_text() -> None:
    html = render_cotton('<c-panel-applied-filter label="Status: Inactive" />')

    assert "Status: Inactive" in html


def test_applied_filter_close_icon_is_decorative() -> None:
    html = render_cotton('<c-panel-applied-filter label="Status: Inactive" />')

    assert re.search(
        r'<span aria-hidden="true"[^>]*>\s*<svg[^>]*aria-label="close"', html
    )


def test_applied_filter_attrs_land_on_the_remove_button() -> None:
    html = render_cotton(
        '<c-panel-applied-filter label="Status: Inactive" hx-delete="/filters/status/" />'
    )

    button_start = html.index("<button")
    button_end = html.index(">", button_start)

    assert 'hx-delete="/filters/status/"' in html[button_start:button_end]


def test_applied_filter_label_is_escaped() -> None:
    html = render_cotton('<c-panel-applied-filter label="<script>alert(1)</script>" />')

    assert "<script>alert(1)</script>" not in html


def test_filter_toggle_pressed_false_string_is_not_pressed() -> None:
    html = render_cotton('<c-panel-filter-toggle label="Active" pressed="False" />')

    assert 'aria-pressed="false"' in html
    assert "<svg" not in html


def test_search_field_label_hidden_false_string_keeps_the_label_visible() -> None:
    html = render_cotton(
        '<c-panel-search-field name="q" label="Search learners" label_hidden="False" />'
    )

    label_match = re.search(r'<label[^>]*class="([^"]*)"', html)

    assert label_match is not None
    assert "sr-only" not in label_match.group(1)
