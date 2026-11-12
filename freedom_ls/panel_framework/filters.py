"""Declared table filters: a table's own narrowing controls, applied on top
of its search and sort.

Filters follow `PanelAction`'s shape: class attributes hold configuration
that never varies per declaration, `__init__` holds what does.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Literal

from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone


class TableFilter:
    """One control in a table's toolbar: a key, a label, and the lookup its
    values narrow the queryset by.

    `always_shown` decides whether the filter renders as a pill with no
    value set, or only appears once applied (via a link) or opened from
    "Add filter". `default` is the selection used whenever the request's own
    selection is empty: the parameter absent, empty, or holding no valid
    value. A filter with a default therefore always has a selection, so its
    chip has no remove control and "Clear all" returns it to the default.
    """

    always_shown: bool = False
    #: How the toolbar and the mobile sheet render this filter's choices:
    #: "chips" for a toggle group, "select" for a <select>,
    #: "grouped_checklist" for a checkbox per choice under the headings
    #: `get_groups` returns, for a filter with many values. Only the
    #: control; `multiple` decides how many values the filter holds.
    widget: Literal["chips", "select", "grouped_checklist"] = "chips"
    #: Whether several values may be selected at once. A single-select filter
    #: replaces its selection on toggle and keeps only the first valid value
    #: from the query string.
    multiple: bool = True

    def __init__(
        self,
        key: str,
        label: str,
        *,
        lookup: str = "",
        always_shown: bool = False,
        default: tuple[str, ...] = (),
    ) -> None:
        self.key = key
        self.label = label
        self.lookup = lookup
        self.always_shown = always_shown
        self.default = default

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        """Every value this filter accepts, as `(value, label)` pairs."""
        raise NotImplementedError

    def get_groups(
        self, request: HttpRequest
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        """The choices under headings, for the grouped checklist widget: one
        unnamed group holding every choice unless a filter says otherwise."""
        return [("", self.get_choices(request))]

    def validate(
        self,
        values: list[str],
        request: HttpRequest,
        choices: list[tuple[str, str]] | None = None,
    ) -> list[str]:
        """The subset of `values` this filter accepts.

        A value that isn't one of `get_choices`' own is dropped rather than
        raising, since it reaches here straight from the query string and may
        be guessed, stale, or scoped to a request that no longer applies.
        `choices` is this request's `get_choices` result when the caller
        already has it, so a filter whose choices come from a query is not
        asked again.
        """
        if choices is None:
            choices = self.get_choices(request)
        allowed = {value for value, _ in choices}
        kept = [value for value in values if value in allowed]
        return kept if self.multiple else kept[:1]

    def toggled(self, values: list[str], value: str) -> list[str]:
        """The selection a choice link for `value` leads to: `value` removed
        if selected, appended if not; for a single-select filter, `value`
        alone."""
        if not self.multiple:
            return [value]
        if value in values:
            return [existing for existing in values if existing != value]
        return [*values, value]

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        """`queryset` narrowed to `values`. The request is there for a filter
        whose narrowing depends on who is asking or on the page's scope."""
        return queryset.filter(**{f"{self.lookup}__in": values})


class ChoiceFilter(TableFilter):
    """A filter over a fixed, or per-request, set of choices."""

    def __init__(
        self,
        key: str,
        label: str,
        *,
        lookup: str = "",
        choices: list[tuple[str, str]] | None = None,
        always_shown: bool = False,
        default: tuple[str, ...] = (),
    ) -> None:
        super().__init__(
            key, label, lookup=lookup, always_shown=always_shown, default=default
        )
        self.choices = choices or []

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return self.choices


class RelatedChoiceFilter(TableFilter):
    """A filter whose choices come from another model's rows.

    `get_queryset` must be scoped the same way `DataTable.get_queryset` is,
    so a value outside that scope is invisible to `get_choices` and
    `validate` drops it.
    """

    widget: Literal["chips", "select", "grouped_checklist"] = "select"

    def __init__(
        self,
        key: str,
        label: str,
        *,
        lookup: str = "",
        queryset: QuerySet | None = None,
        always_shown: bool = False,
        default: tuple[str, ...] = (),
    ) -> None:
        super().__init__(
            key, label, lookup=lookup, always_shown=always_shown, default=default
        )
        self._queryset = queryset

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        if self._queryset is None:
            raise NotImplementedError
        return self._queryset

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return [(str(obj.pk), str(obj)) for obj in self.get_queryset(request)]


class BooleanFilter(TableFilter):
    """A single on/off toggle: narrows when its parameter is present with
    value "1", and does nothing when absent."""

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return [("1", self.label)]

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        if "1" in values:
            return queryset.filter(**{self.lookup: True})
        return queryset


class ToggleFilter(TableFilter):
    """A single on/off switch that narrows nothing itself. It switches
    something on that the table then reads from its own query state, where
    `BooleanFilter` narrows the queryset by a field."""

    def __init__(self, key: str, label: str) -> None:
        super().__init__(key, label)

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return [("1", self.label)]

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        return queryset


class PeriodFilter(ChoiceFilter):
    """Rows whose `field` falls in the last N calendar days, today included,
    counted from midnight in the project's time zone: "Last 7 days" is today
    and the six days before it."""

    widget = "select"
    multiple = False

    def __init__(
        self,
        key: str,
        label: str,
        field: str,
        presets: Mapping[str, tuple[str, int]],
    ) -> None:
        """`presets` maps each URL value to its `(label, days)`."""
        super().__init__(
            key,
            label,
            lookup=field,
            choices=[(value, text) for value, (text, _days) in presets.items()],
        )
        self.field = field
        self.presets = presets

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        days = [self.presets[value][1] for value in values if value in self.presets]
        if not days:
            # A stale or hand-edited URL value must not hide every row.
            return queryset
        midnight = timezone.localtime(timezone.now()).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start = midnight - timedelta(days=days[0] - 1)
        return queryset.filter(**{f"{self.field}__gte": start})
