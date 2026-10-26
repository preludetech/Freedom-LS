"""Tests for the query-string paging helpers."""

from __future__ import annotations

import pytest

from freedom_ls.base.pagination import clamped_page, page_href, position_text

PATH = "/dashboard/"
PARAM = "page_available"


def test_a_link_preserves_every_other_pagers_page(rf):
    request = rf.get(PATH, {"page_available": "2", "page_history": "3"})

    href = page_href(request, PARAM, 3)

    assert "page_available=3" in href
    assert "page_history=3" in href


def test_a_page_one_link_drops_its_own_parameter(rf):
    request = rf.get(PATH, {"page_available": "2", "page_history": "3"})

    href = page_href(request, PARAM, 1)

    assert "page_available" not in href
    assert "page_history=3" in href


def test_a_link_carries_an_unrecognised_parameter_through(rf):
    request = rf.get(PATH, {"utm_source": "newsletter"})

    href = page_href(request, PARAM, 2)

    assert "utm_source=newsletter" in href
    assert "page_available=2" in href


def test_a_page_one_link_with_nothing_else_is_the_bare_path(rf):
    request = rf.get(PATH)

    assert page_href(request, PARAM, 1) == PATH


@pytest.mark.parametrize("raw", ["abc", "0", "-1"])
def test_a_junk_or_below_range_page_number_clamps_to_page_one(rf, raw):
    request = rf.get(PATH, {PARAM: raw})

    page = clamped_page(request, PARAM, list(range(10)), 3)

    assert page.number == 1


def test_a_page_number_past_the_end_clamps_to_the_last_page(rf):
    request = rf.get(PATH, {PARAM: "9999"})

    page = clamped_page(request, PARAM, list(range(10)), 3)

    assert page.number == 4


def test_a_missing_page_parameter_gives_page_one(rf):
    request = rf.get(PATH)

    page = clamped_page(request, PARAM, list(range(10)), 3)

    assert page.number == 1


def test_a_valid_page_number_is_honoured(rf):
    request = rf.get(PATH, {PARAM: "2"})

    page = clamped_page(request, PARAM, list(range(10)), 3)

    assert page.number == 2
    assert list(page.object_list) == [3, 4, 5]


def test_position_text_words_the_range_a_page_shows(rf):
    request = rf.get(PATH, {PARAM: "2"})

    page = clamped_page(request, PARAM, list(range(4)), 3)

    assert position_text(page) == "4 to 4 of 4"


def test_without_a_request_a_link_is_the_query_string_alone():
    assert page_href(None, PARAM, 2) == "?page_available=2"
    assert page_href(None, PARAM, 1) == ""
