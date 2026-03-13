from __future__ import annotations

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.template.loader import render_to_string


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
        cls, request: HttpRequest, columns: list[dict], filters: dict | None = None
    ) -> Page:
        queryset = cls.get_queryset(request)
        if filters:
            queryset = queryset.filter(**filters)

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
        page_obj = paginator.get_page(page_number)

        return page_obj

    @classmethod
    def render(
        cls,
        request: HttpRequest,
        filters: dict | None = None,
        base_url: str = "",
        table_id: str = "data-table-container",
    ) -> str:
        columns = cls._prepare_columns()
        sort_by = request.GET.get("sort", "")
        sort_order = request.GET.get("order", "asc")
        search_query = request.GET.get("search", "").strip()
        page_obj = cls.get_rows(request, columns, filters=filters)
        context = {
            "columns": columns,
            "rows": page_obj,
            "page_obj": page_obj,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "base_url": base_url,
            "show_search": bool(cls.search_fields),
            "search_query": search_query,
            "table_id": table_id,
        }
        return render_to_string(
            "panel_framework/partials/list_view.html", context, request=request
        )
