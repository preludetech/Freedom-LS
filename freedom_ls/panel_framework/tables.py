from __future__ import annotations

from dataclasses import dataclass, field

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest


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
            params[self.param("search")] = [self.search]
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


class DataTable:
    """Abstract class used for rendering data tables"""

    page_size = 25
    search_fields: list[str] = []

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        raise NotImplementedError

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        raise NotImplementedError

    @classmethod
    def _prepare_columns(cls) -> list[dict[str, object]]:
        """Enrich columns: derive sort_field from text_attr/attr for sortable columns."""
        columns: list[dict[str, object]] = cls.get_columns()
        for col in columns:
            if col.get("sortable") and "sort_field" not in col:
                attr = col.get("text_attr") or col.get("attr", "")
                if isinstance(attr, str):
                    col["sort_field"] = attr.replace(".", "__")
        return columns

    @classmethod
    def parse_query(cls, request: HttpRequest, key: str) -> TableQuery:
        """This table's own state from the request, keyed by `key`.

        Only the page number is read under its prefixed name so far — search
        and sort still read the old unprefixed `search`/`sort`/`order` names
        two tables on one page would collide on, until every table's state is
        namespaced by key.
        """
        page = request.GET.get(f"{key}-page", "1")
        search = request.GET.get("search", "").strip()
        sort_field = request.GET.get("sort", "")
        order = request.GET.get("order", "asc")
        sort = f"-{sort_field}" if sort_field and order == "desc" else sort_field
        return TableQuery(key=key, search=search, sort=sort, page=page)

    @classmethod
    def filter_queryset(
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> QuerySet:
        """Search then sort `queryset` from `query`. Narrowing only — pagination
        is `get_rows`'s job, so this stays reusable wherever a table's full,
        unpaginated result set is needed (an export, a bulk action).
        """
        if query.search and cls.search_fields:
            search_filter = Q()
            for search_field in cls.search_fields:
                search_filter |= Q(**{f"{search_field}__icontains": query.search})
            queryset = queryset.filter(search_filter)

        columns = cls._prepare_columns()
        sortable_fields = {col["sort_field"] for col in columns if col.get("sortable")}
        sort_field = query.sort[1:] if query.sort.startswith("-") else query.sort
        if sort_field in sortable_fields:
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
        columns = cls._prepare_columns()
        page_obj = cls.get_rows(request, queryset, query)
        return {
            "columns": columns,
            "rows": page_obj,
            "page_obj": page_obj,
            "query": query,
            "base_url": base_url,
            "page_url": page_url,
            "region_id": region_id,
            "pagination": page_links(page_obj, query),
            # The old, unprefixed names the region template still renders
            # from until slice 2 moves sort and search onto `query`.
            "sort_by": request.GET.get("sort", ""),
            "sort_order": request.GET.get("order", "asc"),
            "show_search": bool(cls.search_fields),
            "search_query": request.GET.get("search", "").strip(),
        }
