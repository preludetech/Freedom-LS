"""A table that declares export columns serves a streamed, formula-safe CSV
of its rows, honouring search, filters and sort but never pagination."""

from __future__ import annotations

import csv
import io

import pytest

from django.contrib.sites.models import Site
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.utils import timezone

from freedom_ls.site_aware_models.models import _thread_locals

from .conftest import _make_stub
from .view_helpers import fetch

pytestmark = pytest.mark.django_db


def _panel_path(stub_pk: object) -> str:
    return f"stubs/{stub_pk}/__tabs/default"


def _rows(response: HttpResponse | StreamingHttpResponse) -> list[list[str]]:
    assert isinstance(response, StreamingHttpResponse)
    body = b"".join(response.streaming_content).decode("utf-8")
    return list(csv.reader(io.StringIO(body.removeprefix("\ufeff"))))


def test_export_honours_search_filters_and_sort_without_pagination(
    mock_site_context: Site,
) -> None:
    kinds = ["b" if i % 3 else "a" for i in range(60)]
    stubs = [_make_stub(name=f"row-{i:02d}", kind=kind) for i, kind in enumerate(kinds)]
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
    stub = _make_stub(name="=cmd", kind="a")

    response = fetch(_panel_path(stub.pk), data={"stub-export": "csv"})

    header, (name_cell, kind_cell) = _rows(response)
    assert header == ["Name", "Kind"]
    assert name_cell == "'=cmd"
    assert kind_cell == "Alpha"


def test_bom_and_headers(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x", kind="a")

    response = fetch(_panel_path(stub.pk), data={"stub-export": "csv"})

    assert response["Content-Type"] == "text/csv; charset=utf-8"
    today = timezone.localdate().isoformat()
    expected_disposition = f'attachment; filename="stub-{today}.csv"'
    assert response["Content-Disposition"] == expected_disposition
    assert isinstance(response, StreamingHttpResponse)
    body = b"".join(response.streaming_content)
    assert body.startswith("\ufeff".encode())


def test_no_export_columns_is_404(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x")
    child_path = f"stubs/{stub.pk}/__tabs/children"

    with pytest.raises(Http404):
        fetch(child_path, data={"children-export": "csv"})


def test_unknown_export_format_is_404(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-x")

    with pytest.raises(Http404):
        fetch(_panel_path(stub.pk), data={"stub-export": "xlsx"})


def test_export_stays_scoped_when_site_thread_local_cleared(
    mock_site_context: Site,
) -> None:
    stubs = [_make_stub(name=f"row-{i:02d}") for i in range(3)]

    response = fetch(_panel_path(stubs[0].pk), data={"stub-export": "csv"})
    delattr(_thread_locals, "request")

    _header, *body = _rows(response)
    names = [row[0] for row in body]
    assert names == sorted(stub.name for stub in stubs)
