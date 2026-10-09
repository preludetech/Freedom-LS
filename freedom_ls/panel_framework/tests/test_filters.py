"""Unit tests for the declared filter kinds: what values each accepts and
how each narrows a queryset, exercised through StubDataTable and
StubChildDataTable so they run against a real queryset."""

from __future__ import annotations

import pytest

from django.test import RequestFactory

from .helpers import make_stub
from .stub_panels import StubChildDataTable, StubDataTable

pytestmark = pytest.mark.django_db


def test_choice_filter_narrows_rows() -> None:
    make_stub(name="alpha-row", kind="a")
    make_stub(name="beta-row", kind="b")
    request = RequestFactory().get("/", {"stub-kind": "a"})

    query = StubDataTable.parse_query(request, "stub")
    rows = StubDataTable.filter_queryset(
        request, StubDataTable.get_queryset(request), query
    )

    assert [row.name for row in rows] == ["alpha-row"]


def test_boolean_filter_narrows_only_when_1() -> None:
    make_stub(name="active-row", is_active=True)
    make_stub(name="inactive-row", is_active=False)
    request = RequestFactory().get("/", {"stub-active": "1"})

    query = StubDataTable.parse_query(request, "stub")
    rows = StubDataTable.filter_queryset(
        request, StubDataTable.get_queryset(request), query
    )

    assert [row.name for row in rows] == ["active-row"]


def test_boolean_filter_does_not_narrow_when_absent() -> None:
    make_stub(name="active-row", is_active=True)
    make_stub(name="inactive-row", is_active=False)
    request = RequestFactory().get("/")

    query = StubDataTable.parse_query(request, "stub")
    rows = StubDataTable.filter_queryset(
        request, StubDataTable.get_queryset(request), query
    )

    assert {row.name for row in rows} == {"active-row", "inactive-row"}


def test_related_choice_filter_choices_are_scoped() -> None:
    in_scope = make_stub(name="in-scope-parent")
    make_stub(name="out-of-scope-parent")
    request = RequestFactory().get("/")

    (parent_filter,) = StubChildDataTable.get_filters()

    assert parent_filter.get_choices(request) == [(str(in_scope.pk), "in-scope-parent")]


def test_related_choice_filter_drops_pk_outside_scope() -> None:
    in_scope = make_stub(name="in-scope-parent")
    out_of_scope = make_stub(name="out-of-scope-parent")
    request = RequestFactory().get("/")

    (parent_filter,) = StubChildDataTable.get_filters()
    validated = parent_filter.validate(
        [str(in_scope.pk), str(out_of_scope.pk)], request
    )

    assert validated == [str(in_scope.pk)]
