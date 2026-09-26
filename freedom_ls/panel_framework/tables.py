from __future__ import annotations

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest


class DataTable:
    """Abstract class used for rendering data tables"""

    page_size = 5
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
    def get_rows(
        cls, request: HttpRequest, columns: list[dict], queryset: QuerySet
    ) -> Page:
        """Search, sort and paginate `queryset` from the request's query string.

        The queryset arrives already scoped: whoever renders the table owns
        which rows it may show, and this method only narrows them further.
        """
        search_query = request.GET.get("search", "").strip()
        if search_query and cls.search_fields:
            search_filter = Q()
            for field in cls.search_fields:
                search_filter |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(search_filter)

        sort_by = request.GET.get("sort", "")
        sort_order = request.GET.get("order", "asc")
        sortable_fields = {col["sort_field"] for col in columns if col.get("sortable")}
        if sort_by in sortable_fields:
            order_expr = f"-{sort_by}" if sort_order == "desc" else sort_by
            queryset = queryset.order_by(order_expr)

        page_number = request.GET.get("page", 1)
        paginator = Paginator(queryset, cls.page_size)
        return paginator.get_page(page_number)

    @classmethod
    def get_context(
        cls,
        request: HttpRequest,
        queryset: QuerySet,
        base_url: str,
        table_id: str,
    ) -> dict[str, object]:
        """Everything the table's region template needs to render one page."""
        columns = cls._prepare_columns()
        page_obj = cls.get_rows(request, columns, queryset)
        return {
            "columns": columns,
            "rows": page_obj,
            "page_obj": page_obj,
            "sort_by": request.GET.get("sort", ""),
            "sort_order": request.GET.get("order", "asc"),
            "base_url": base_url,
            "show_search": bool(cls.search_fields),
            "search_query": request.GET.get("search", "").strip(),
            "table_id": table_id,
        }
