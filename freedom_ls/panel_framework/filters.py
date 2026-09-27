"""Declared table filters: a table's own narrowing controls, applied on top
of its search and sort.

Filters follow `PanelAction`'s shape: class attributes hold configuration
that never varies per declaration, `__init__` holds what does.
"""

from __future__ import annotations

from typing import Literal

from django.db.models import QuerySet
from django.http import HttpRequest


class TableFilter:
    """One control in a table's toolbar: a key, a label, and the lookup its
    values narrow the queryset by.

    `always_shown` decides whether the filter renders as a pill with no
    value set, or only appears once applied (via a link) or opened from
    "Add filter".
    """

    always_shown: bool = False
    #: How the mobile sheet renders this filter's choices: "chips" for a
    #: multi-select toggle group, "select" for a single-value <select>.
    widget: Literal["chips", "select"] = "chips"

    def __init__(
        self, key: str, label: str, *, lookup: str, always_shown: bool = False
    ) -> None:
        self.key = key
        self.label = label
        self.lookup = lookup
        self.always_shown = always_shown

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        """Every value this filter accepts, as `(value, label)` pairs."""
        raise NotImplementedError

    def validate(self, values: list[str], request: HttpRequest) -> list[str]:
        """The subset of `values` this filter accepts.

        A value that isn't one of `get_choices`' own is dropped rather than
        raising, since it reaches here straight from the query string and may
        be guessed, stale, or scoped to a request that no longer applies.
        """
        allowed = {value for value, _ in self.get_choices(request)}
        return [value for value in values if value in allowed]

    def apply(self, queryset: QuerySet, values: list[str]) -> QuerySet:
        return queryset.filter(**{f"{self.lookup}__in": values})


class ChoiceFilter(TableFilter):
    """A filter over a fixed, or per-request, set of choices."""

    def __init__(
        self,
        key: str,
        label: str,
        *,
        lookup: str,
        choices: list[tuple[str, str]] | None = None,
        always_shown: bool = False,
    ) -> None:
        super().__init__(key, label, lookup=lookup, always_shown=always_shown)
        self.choices = choices or []

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return self.choices


class RelatedChoiceFilter(TableFilter):
    """A filter whose choices come from another model's rows.

    `get_queryset` must be scoped the same way `DataTable.get_queryset` is,
    so a value outside that scope is invisible to `get_choices` and
    `validate` drops it.
    """

    widget: Literal["chips", "select"] = "select"

    def __init__(
        self,
        key: str,
        label: str,
        *,
        lookup: str,
        queryset: QuerySet | None = None,
        always_shown: bool = False,
    ) -> None:
        super().__init__(key, label, lookup=lookup, always_shown=always_shown)
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

    def apply(self, queryset: QuerySet, values: list[str]) -> QuerySet:
        if "1" in values:
            return queryset.filter(**{self.lookup: True})
        return queryset
