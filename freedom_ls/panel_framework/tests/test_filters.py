"""Unit tests for the declared filter kinds: what values each accepts and
how each narrows a queryset, exercised through StubDataTable and
StubChildDataTable so they run against a real queryset."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import pytest
import time_machine

from django.test import RequestFactory

from freedom_ls.panel_framework.filters import (
    BooleanFilter,
    ChoiceFilter,
    PeriodFilter,
    RelatedChoiceFilter,
    TableFilter,
    ToggleFilter,
)
from freedom_ls.panel_framework.tables import DataTable, _toolbar_entry

from .helpers import make_stub
from .stub_models import StubModel
from .stub_panels import StubChildDataTable, StubDataTable, StubPlainDataTable

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


class _OneKindFilter(ChoiceFilter):
    multiple = False


def _one_kind_filter() -> _OneKindFilter:
    return _OneKindFilter(
        "kind", "Kind", lookup="kind", choices=[("a", "A"), ("b", "B")]
    )


def test_a_single_select_filter_keeps_only_the_first_valid_value() -> None:
    request = RequestFactory().get("/")

    assert _one_kind_filter().validate(["nope", "b", "a"], request) == ["b"]


def test_a_single_select_filter_toggles_by_replacing_the_selection() -> None:
    assert _one_kind_filter().toggled(["a"], "b") == ["b"]
    assert _one_kind_filter().toggled(["a"], "a") == ["a"]


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


_PRESETS = {
    "today": ("Today", 1),
    "7d": ("Last 7 days", 7),
    "30d": ("Last 30 days", 30),
}


def _at(moment: datetime, **fields: object) -> StubModel:
    """A stub row created at `moment`."""
    return make_stub(created_at=moment, **fields)


def test_toggle_filter_returns_its_queryset_unchanged() -> None:
    make_stub(is_active=False)
    queryset = StubModel.objects.all()

    result = ToggleFilter("inactive", "Show inactive").apply(
        RequestFactory().get("/"), queryset, ["1"]
    )

    assert result is queryset


def test_toggle_filter_offers_one_choice_labelled_with_its_label() -> None:
    filter_ = ToggleFilter("inactive", "Show inactive")

    assert filter_.get_choices(RequestFactory().get("/")) == [("1", "Show inactive")]


def test_the_period_filter_offers_its_presets_in_order_and_no_default() -> None:
    period = PeriodFilter("when", "When", "created_at", _PRESETS)

    assert period.get_choices(RequestFactory().get("/")) == [
        ("today", "Today"),
        ("7d", "Last 7 days"),
        ("30d", "Last 30 days"),
    ]
    assert period.default == ()
    assert period.toggled(["7d"], "30d") == ["30d"]


def test_two_period_values_in_the_query_string_keep_only_the_first() -> None:
    period = PeriodFilter("when", "When", "created_at", _PRESETS)

    assert period.validate(["today", "30d"], RequestFactory().get("/")) == ["today"]


@pytest.mark.parametrize(("preset", "days"), [("today", 1), ("7d", 7), ("30d", 30)])
def test_each_period_preset_covers_that_many_calendar_days_ending_today(
    preset: str, days: int
) -> None:
    """ "Last 7 days" is today and the six days before it, so the window
    starts at midnight `days - 1` days ago."""
    period = PeriodFilter("when", "When", "created_at", _PRESETS)
    days_back = timedelta(days=days - 1)
    inside = _at(datetime(2026, 10, 24, 0, 0, tzinfo=UTC) - days_back)
    _at(datetime(2026, 10, 23, 23, 59, 59, tzinfo=UTC) - days_back)

    with time_machine.travel(datetime(2026, 10, 24, 15, 30, tzinfo=UTC), tick=False):
        result = period.apply(
            RequestFactory().get("/"), StubModel.objects.all(), [preset]
        )

    assert set(result) == {inside}


def test_the_period_midnight_is_midnight_in_the_project_time_zone(settings) -> None:
    settings.TIME_ZONE = "Africa/Johannesburg"
    period = PeriodFilter("when", "When", "created_at", _PRESETS)
    # Johannesburg is UTC+2, so local midnight on the 24th is 22:00 UTC on the 23rd.
    before = _at(datetime(2026, 10, 23, 21, 59, tzinfo=UTC))
    after = _at(datetime(2026, 10, 23, 22, 0, tzinfo=UTC))

    with time_machine.travel(datetime(2026, 10, 24, 10, 0, tzinfo=UTC), tick=False):
        result = set(
            period.apply(RequestFactory().get("/"), StubModel.objects.all(), ["today"])
        )

    assert (before in result, after in result) == (False, True)


def test_the_period_filter_filters_on_the_field_it_is_given() -> None:
    period = PeriodFilter("seen", "Seen", "seen_at", _PRESETS)
    recent = make_stub(seen_at=datetime(2026, 10, 24, 9, 0, tzinfo=UTC))
    make_stub(seen_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC))
    make_stub(seen_at=None)
    # created_at is outside the window for every row, so a filter reading it
    # would return nothing.
    StubModel.objects.update(created_at=datetime(2020, 1, 1, tzinfo=UTC))

    with time_machine.travel(datetime(2026, 10, 24, 15, 0, tzinfo=UTC), tick=False):
        result = period.apply(
            RequestFactory().get("/"), StubModel.objects.all(), ["7d"]
        )

    assert set(result) == {recent}


def test_an_unknown_period_value_leaves_every_row_in_place() -> None:
    period = PeriodFilter("when", "When", "created_at", _PRESETS)
    make_stub(created_at=datetime(2020, 1, 1, tzinfo=UTC))
    make_stub(created_at=datetime(2026, 10, 24, tzinfo=UTC))

    result = period.apply(RequestFactory().get("/"), StubModel.objects.all(), ["99y"])

    assert result.count() == 2


# Every filter kind, built over StubModel with one value it accepts.


def _choice_case() -> tuple[TableFilter, str]:
    return ChoiceFilter("kind", "Kind", lookup="kind", choices=[("a", "A")]), "a"


def _related_case() -> tuple[TableFilter, str]:
    parent = make_stub(name="related-parent")
    return (
        RelatedChoiceFilter(
            "parent", "Parent", lookup="pk", queryset=StubModel.objects.all()
        ),
        str(parent.pk),
    )


def _related_with_default_case() -> tuple[TableFilter, str]:
    parent = make_stub(name="defaulted-parent")
    return (
        RelatedChoiceFilter(
            "parent",
            "Parent",
            lookup="pk",
            queryset=StubModel.objects.all(),
            default=(str(parent.pk),),
        ),
        str(parent.pk),
    )


def _boolean_case() -> tuple[TableFilter, str]:
    return BooleanFilter("active", "Active", lookup="is_active"), "1"


def _toggle_case() -> tuple[TableFilter, str]:
    return ToggleFilter("inactive", "Show inactive"), "1"


def _period_case() -> tuple[TableFilter, str]:
    return PeriodFilter("when", "When", "created_at", _PRESETS), "7d"


_FILTER_CASES = [
    pytest.param(_choice_case, id="choice"),
    pytest.param(_related_case, id="related"),
    pytest.param(_related_with_default_case, id="related-with-default"),
    pytest.param(_boolean_case, id="boolean"),
    pytest.param(_toggle_case, id="toggle"),
    pytest.param(_period_case, id="period"),
]
_WIDGETS = ["chips", "select", "grouped_checklist"]

FilterCase = Callable[[], tuple[TableFilter, str]]


def _table_over(filter_: TableFilter, widget: str) -> type[DataTable]:
    filter_.widget = cast(Literal["chips", "select", "grouped_checklist"], widget)

    class _FilteredTable(StubPlainDataTable):
        @classmethod
        def get_filters(cls) -> list[TableFilter]:
            return [filter_]

    return _FilteredTable


@pytest.mark.parametrize("widget", _WIDGETS)
@pytest.mark.parametrize("case", _FILTER_CASES)
def test_a_filters_state_is_read_from_its_tables_url_parameter(
    case: FilterCase, widget: str
) -> None:
    filter_, value = case()
    table = _table_over(filter_, widget)
    request = RequestFactory().get("/", {f"t-{filter_.key}": value})

    query = table.parse_query(request, "t")
    entry = _toolbar_entry(request, query, filter_)

    assert query.filters == {filter_.key: [value]}
    assert entry["values"] == [value]
    selected = [
        choice["value"]
        for choice in cast(list[dict[str, object]], entry["choices"])
        if choice["selected"]
    ]
    assert selected == [value]


@pytest.mark.parametrize("widget", _WIDGETS)
@pytest.mark.parametrize("case", _FILTER_CASES)
def test_a_choice_toggles_on_and_off(case: FilterCase, widget: str) -> None:
    filter_, value = case()
    table = _table_over(filter_, widget)
    off = table.parse_query(RequestFactory().get("/"), "t")
    on = table.parse_query(RequestFactory().get("/", {f"t-{filter_.key}": value}), "t")
    param = off.param(filter_.key)

    turned_on = off.filter_changes(filter_.key, filter_.toggled([], value))
    # A single-select filter replaces its selection, so its way off is the
    # chip's remove control.
    turned_off_values = filter_.toggled([value], value) if filter_.multiple else []
    turned_off = on.filter_changes(filter_.key, turned_off_values)

    assert turned_on[param] == [value]
    assert turned_off[param] is None


@pytest.mark.parametrize("widget", _WIDGETS)
@pytest.mark.parametrize("case", _FILTER_CASES)
def test_another_tables_parameters_are_left_alone(
    case: FilterCase, widget: str
) -> None:
    filter_, value = case()
    table = _table_over(filter_, widget)
    request = RequestFactory().get(
        "/", {f"t-{filter_.key}": value, f"other-{filter_.key}": "x", "other-q": "y"}
    )

    query = table.parse_query(request, "t")
    changes = query.filter_changes(filter_.key, filter_.toggled([value], value))
    entry = _toolbar_entry(request, query, filter_)

    assert set(changes) == {f"t-{filter_.key}", "t-page"}
    assert set(query.to_params()) == {f"t-{filter_.key}", "t-page"}
    if widget == "grouped_checklist":
        carried = cast(list[tuple[str, str]], entry["form_hidden_inputs"])
        assert {(f"other-{filter_.key}", "x"), ("other-q", "y")} <= set(carried)


@pytest.mark.parametrize("widget", _WIDGETS)
def test_an_unknown_period_value_is_ignored_with_no_error(widget: str) -> None:
    make_stub(created_at=datetime(2020, 1, 1, tzinfo=UTC))
    filter_ = PeriodFilter("when", "When", "created_at", _PRESETS)
    table = _table_over(filter_, widget)
    request = RequestFactory().get("/", {"t-when": "99y"})

    query = table.parse_query(request, "t")
    rows = table.filter_queryset(request, table.get_queryset(request), query)

    assert query.filters == {}
    assert rows.count() == 1
