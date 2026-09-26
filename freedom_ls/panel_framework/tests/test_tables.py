"""Unit tests for TableQuery: parsing a table's own state from a request and
serialising it back into prefixed query parameters."""

from __future__ import annotations

from django.test import RequestFactory

from .stub_panels import StubDataTable


def test_table_query_to_params_round_trips() -> None:
    request = RequestFactory().get("/", {"stub-page": "3", "stub-zzz": "nope"})

    query = StubDataTable.parse_query(request, "stub")

    assert query.to_params() == {"stub-page": ["3"]}
