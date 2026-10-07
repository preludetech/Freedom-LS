from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from django.core.paginator import Page, Paginator
from django.db.models import Model, Q, QuerySet
from django.http import HttpRequest
from django.utils.functional import SimpleLazyObject

from freedom_ls.base.csv_safety import escape_csv_formula
from freedom_ls.panel_framework.filters import TableFilter
from freedom_ls.panel_framework.templatetags.data_table_tags import getattr_str


@dataclass(frozen=True)
class TableQuery:
    """One table's own slice of the request's query string, keyed so two
    tables on the same page never read each other's parameters."""

    key: str
    search: str = ""
    sort: str = ""  # a sort_field, "-" prefix for descending
    page: str = "1"  # raw; Paginator.get_page clamps it
    filters: dict[str, list[str]] = field(default_factory=dict)

    def param(self, name: str) -> str:
        """This table's own name for a bare parameter name, e.g. "page"."""
        return f"{self.key}-{name}"

    def to_params(self) -> dict[str, list[str]]:
        """This query's current state as prefixed GET parameters.

        Only non-empty values are included, so a table with nothing set
        contributes nothing to a query string built from it.
        """
        params: dict[str, list[str]] = {}
        if self.search:
            params[self.param("q")] = [self.search]
        if self.sort:
            params[self.param("sort")] = [self.sort]
        if self.page:
            params[self.param("page")] = [self.page]
        for filter_key, values in self.filters.items():
            if values:
                params[self.param(filter_key)] = values
        return params

    def page_changes(self, number: int) -> dict[str, object]:
        """The `{% querystring %}` changes that link to page `number`."""
        return {self.param("page"): number}

    def sort_changes(self, column: Column) -> dict[str, object]:
        """The `{% querystring %}` changes that sort by `column`, flipping
        its direction when it is already the sorted column. Sorting always
        returns to page 1, since the current page may not exist in the new
        order."""
        currently_ascending = self.sort == column.sort_field
        next_sort = (
            f"-{column.sort_field}" if currently_ascending else column.sort_field
        )
        return {self.param("sort"): next_sort, self.param("page"): None}

    def filter_changes(self, filter_key: str, values: list[str]) -> dict[str, object]:
        """The `{% querystring %}` changes that set `filter_key` to `values`,
        clearing it when `values` is empty. Filtering always returns to page
        1, since the current page may not exist once the rows are narrowed."""
        return {self.param(filter_key): values or None, self.param("page"): None}

    def clear_filters_changes(self, filter_keys: list[str]) -> dict[str, object]:
        """The `{% querystring %}` changes "Clear all" applies: every filter
        removed and the page reset. Search and sort are left alone."""
        changes: dict[str, object] = {self.param(key): None for key in filter_keys}
        changes[self.param("page")] = None
        return changes


def page_links(page_obj: Page, query: TableQuery) -> dict[str, object]:
    """The previous/next/numbered links a table's pagination control renders.

    Each link carries only the `{% querystring %}` changes needed to reach
    it, so applying it on top of the current query string leaves every other
    table's state, and every other parameter on the page, untouched.
    """

    def _link(number: int) -> dict[str, object]:
        return {"number": number, "changes": query.page_changes(number)}

    pages: list[dict[str, object]] = [
        {**_link(number), "current": number == page_obj.number}
        if isinstance(number, int)
        else {"number": None, "changes": {}, "current": False}
        for number in page_obj.paginator.get_elided_page_range(
            page_obj.number, on_each_side=2, on_ends=2
        )
    ]
    return {
        "previous": (
            _link(page_obj.previous_page_number()) if page_obj.has_previous() else None
        ),
        "next": _link(page_obj.next_page_number()) if page_obj.has_next() else None,
        "pages": pages,
    }


def hidden_inputs(
    request: HttpRequest, query: TableQuery, exclude: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Every current query parameter a table's search or sheet form must
    carry as a hidden input, so submitting it doesn't drop another table's
    state, an unrelated parameter, or this table's own state the form itself
    doesn't already supply.

    Every parameter outside this table's own namespace is carried as-is from
    the request. This table's own state comes from `query.to_params()`
    instead of the raw request, so a value that failed validation (an
    unknown sort, a dropped filter) is never re-submitted, and `exclude`
    leaves out the names the form's own fields already supply.
    """
    prefix = f"{query.key}-"
    excluded_params = {query.param(name) for name in exclude}
    pairs: list[tuple[str, str]] = [
        (name, value)
        for name, values in request.GET.lists()
        if not name.startswith(prefix)
        for value in values
    ]
    for name, values in query.to_params().items():
        if name in excluded_params:
            continue
        pairs.extend((name, value) for value in values)
    return pairs


@dataclass
class Column:
    """One column of a table: what it shows and, if sortable, how it sorts.

    A dataclass, so a typo in a declaration fails loudly instead of quietly
    reading `None` from a dict. A cell template that needs more fields than
    these gets a subclass, declared beside the table that uses it.
    """

    header: str
    template: str
    attr: str = ""
    text_attr: str = ""
    sortable: bool = False
    sort_field: str = ""
    url_name: str = ""
    url_path_template: str = ""
    htmx_nav: bool = False
    #: Open the row in the quick-view drawer instead of navigating to it.
    quick_view: bool = False
    header_class: str = ""
    cell_class: str = ""
    card: Literal["primary", "secondary", "md_only"] = "secondary"

    def __post_init__(self) -> None:
        if self.sortable and not self.sort_field:
            self.sort_field = (self.text_attr or self.attr).replace(".", "__")


@dataclass(frozen=True)
class ExportColumn:
    """One column of a table's CSV export: a header and how to read its
    value from a row. Independent of `Column` — a column may appear on
    screen, in the export, both or neither — so an export can carry a field
    hidden on screen (an email address) and leave out a screen-only one (a
    row-selection checkbox, an action button)."""

    header: str
    value: str | Callable[[Model], object]

    def cell(self, row: Model) -> str:
        if isinstance(self.value, str):
            raw = getattr_str(row, self.value)
        else:
            raw = self.value(row)
        return "" if raw is None else escape_csv_formula(str(raw))


class DataTable:
    """Abstract class used for rendering data tables"""

    page_size = 10
    search_fields: list[str] = []
    #: A template that replaces the default card body (the primary/secondary
    #: cell rendering) below md, for a denser layout than the generic card
    #: gives. `None` keeps the default.
    card_template: str | None = None

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        raise NotImplementedError

    @staticmethod
    def get_columns() -> list[Column]:
        raise NotImplementedError

    @classmethod
    def get_filters(cls) -> list[TableFilter]:
        """Filters this table's rows may be narrowed by, in toolbar order."""
        return []

    @staticmethod
    def get_row_label(row: Model) -> str:
        """One row's accessible name, for its selection checkbox's aria-label."""
        return str(row)

    @classmethod
    def get_export_columns(cls) -> list[ExportColumn]:
        """Columns this table serves through its CSV export, in export
        order. Empty by default, which disables the export for this table.

        Independent of `get_columns()`: a column may read a relation only if
        `get_queryset` already `select_related`s or `prefetch_related`s it,
        so the export's row iterator stays free of per-row queries.
        """
        return []

    @classmethod
    def parse_query(cls, request: HttpRequest, key: str) -> TableQuery:
        """This table's own state from the request, keyed by `key`.

        A sort naming a field none of this table's columns sort by is
        dropped rather than passed through to `order_by`, which would raise
        `FieldError` on a guessed or stale query parameter. A filter value
        that fails its own `validate` is dropped the same way.
        """
        page = request.GET.get(f"{key}-page", "1")
        search = request.GET.get(f"{key}-q", "").strip()
        sort = request.GET.get(f"{key}-sort", "")
        sortable_fields = {
            column.sort_field for column in cls.get_columns() if column.sortable
        }
        sort_field = sort[1:] if sort.startswith("-") else sort
        if sort_field not in sortable_fields:
            sort = ""
        filters: dict[str, list[str]] = {}
        for table_filter in cls.get_filters():
            values = request.GET.getlist(f"{key}-{table_filter.key}")
            validated = table_filter.validate(values, request)
            if validated:
                filters[table_filter.key] = validated
        return TableQuery(key=key, search=search, sort=sort, page=page, filters=filters)

    @classmethod
    def filter_queryset(
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> QuerySet:
        """Search, then apply each declared filter, then sort `queryset` from
        `query`. Narrowing only — pagination is `get_rows`'s job, so this
        stays reusable wherever a table's full, unpaginated result set is
        needed (an export, a bulk action).
        """
        if query.search and cls.search_fields:
            search_filter = Q()
            for search_field in cls.search_fields:
                search_filter |= Q(**{f"{search_field}__icontains": query.search})
            queryset = queryset.filter(search_filter)

        for table_filter in cls.get_filters():
            values = query.filters.get(table_filter.key)
            if values:
                queryset = table_filter.apply(queryset, values)

        if query.sort:
            queryset = queryset.order_by(query.sort)
        return queryset

    @classmethod
    def get_rows(
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> Page:
        """Paginate `queryset`, already searched and sorted, to `query.page`."""
        return Paginator(queryset, cls.page_size).get_page(query.page)

    @classmethod
    def get_context(
        cls,
        request: HttpRequest,
        query: TableQuery,
        queryset: QuerySet,
        *,
        base_url: str,
        page_url: str,
        region_id: str,
    ) -> dict[str, object]:
        """Everything the table's region template needs to render one page."""
        columns = cls.get_columns()
        page_obj = cls.get_rows(request, queryset, query)

        def _sort_state(column: Column) -> Literal["asc", "desc", ""]:
            if query.sort == column.sort_field:
                return "asc"
            if query.sort == f"-{column.sort_field}":
                return "desc"
            return ""

        header_columns = [
            {
                "column": column,
                "changes": query.sort_changes(column) if column.sortable else {},
                "state": _sort_state(column) if column.sortable else "",
            }
            for column in columns
        ]
        sorted_by = next(
            (
                column.header
                for column in columns
                if column.sortable and _sort_state(column)
            ),
            "",
        )
        if page_obj.paginator.count == 0:
            announcement = "No results"
        else:
            announcement = (
                f"Showing {page_obj.start_index()}\u2013{page_obj.end_index()} "
                f"of {page_obj.paginator.count}"
            )
            if sorted_by:
                announcement += f", sorted by {sorted_by}"

        filters = cls.get_filters()
        toolbar = [
            _toolbar_entry(request, query, table_filter) for table_filter in filters
        ]
        filter_keys = [table_filter.key for table_filter in filters]

        primary_column = next(
            (column for column in columns if column.card == "primary"),
            columns[0] if columns else None,
        )
        secondary_columns = [
            column
            for column in columns
            if column is not primary_column and column.card != "md_only"
        ]
        sortable_columns = [column for column in columns if column.sortable]

        # "Reset" clears every filter and the sort, but not the search text —
        # the sheet has no search field of its own, so a search made from the
        # desktop toolbar or the search form stays in place.
        reset_changes = query.clear_filters_changes(filter_keys)
        reset_changes[query.param("sort")] = None

        # The label is lazy: a table with no bulk action never renders it (the
        # checkbox is the only place it's read), and get_row_label defaults to
        # str(row), which would otherwise cost a query per row on a model
        # whose __str__ reads an un-prefetched relation.
        def _lazy_label(row: Model) -> SimpleLazyObject:
            return SimpleLazyObject(lambda: cls.get_row_label(row))

        rows = [{"object": row, "label": _lazy_label(row)} for row in page_obj]
        return {
            "columns": columns,
            "header_columns": header_columns,
            "sorted_by": sorted_by,
            "announcement": announcement,
            "searchable": bool(cls.search_fields),
            "rows": rows,
            "page_obj": page_obj,
            "query": query,
            "base_url": base_url,
            "page_url": page_url,
            "region_id": region_id,
            "pagination": page_links(page_obj, query),
            "hidden_inputs": hidden_inputs(request, query, exclude=("q", "page")),
            "toolbar": toolbar,
            "add_filter": [entry for entry in toolbar if not entry["shown"]],
            "clear_changes": query.clear_filters_changes(filter_keys),
            "any_filter_set": any(entry["values"] for entry in toolbar),
            "exports": bool(cls.get_export_columns()),
            "export_changes": {query.param("export"): "csv"},
            "primary_column": primary_column,
            "secondary_columns": secondary_columns,
            "sortable_columns": sortable_columns,
            "card_template": cls.card_template,
            "sheet_hidden_inputs": hidden_inputs(
                request, query, exclude=("page", "sort", *filter_keys)
            ),
            "reset_changes": reset_changes,
        }


def _toggled(values: list[str], value: str) -> list[str]:
    """`values` with `value` removed if present, appended if not — the
    selection a filter choice link toggles to."""
    if value in values:
        return [existing for existing in values if existing != value]
    return [*values, value]


def _toolbar_entry(
    request: HttpRequest, query: TableQuery, table_filter: TableFilter
) -> dict[str, object]:
    """One filter's toolbar rendering: its current values, their labels, and
    the choices its disclosure lists, each carrying the changes selecting it
    would make."""
    values = query.filters.get(table_filter.key, [])
    choices = table_filter.get_choices(request)
    labels = [label for value, label in choices if value in values]
    return {
        "filter": table_filter,
        "values": values,
        "labels": labels,
        "shown": table_filter.always_shown or bool(values),
        "choices": [
            {
                "value": value,
                "label": label,
                "selected": value in values,
                "changes": query.filter_changes(
                    table_filter.key, _toggled(values, value)
                ),
            }
            for value, label in choices
        ],
        "remove_changes": query.filter_changes(table_filter.key, []),
    }
