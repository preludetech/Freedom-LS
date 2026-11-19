"""Tests for the data_table_tags template tags."""

from __future__ import annotations

import pytest

from freedom_ls.panel_framework.templatetags.data_table_tags import pagination_suffix


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        pytest.param({}, "", id="nothing-to-append"),
        pytest.param(
            {"sort_by": "name"}, "&sort=name&order=asc", id="sort-defaults-to-asc"
        ),
        pytest.param(
            {"sort_by": "name", "sort_order": "desc"},
            "&sort=name&order=desc",
            id="sort-with-order",
        ),
        pytest.param({"sort_order": "desc"}, "", id="order-without-sort-is-dropped"),
        pytest.param(
            {"search_query": "a b&c"}, "&search=a+b%26c", id="search-is-encoded"
        ),
        pytest.param(
            {"extra_params": "registration=abc"},
            "&registration=abc",
            id="extra-params-appended-verbatim",
        ),
        pytest.param(
            {
                "sort_by": "name",
                "sort_order": "desc",
                "search_query": "x",
                "extra_params": "k=v",
            },
            "&sort=name&order=desc&search=x&k=v",
            id="all-in-order",
        ),
    ],
)
def test_pagination_suffix_builds_the_trailing_query_string(
    kwargs: dict[str, str], expected: str
) -> None:
    assert pagination_suffix(**kwargs) == expected
