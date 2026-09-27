"""Unit tests for TableQuery: parsing a table's own state from a request and
serialising it back into prefixed query parameters."""

from __future__ import annotations

from django.test import RequestFactory

from freedom_ls.panel_framework.tables import Column

from .stub_panels import StubDataTable


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
