"""Helpers shared by the API tests, here and in the apps that register endpoints."""

from __future__ import annotations

from django.db import connection
from django.db.models import Model, QuerySet
from django.test.utils import CaptureQueriesContext
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from freedom_ls.api import urls
from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.pagination import DEFAULT_CURSOR_FIELD, ApiKeysetPagination
from freedom_ls.api.scopes import ApiScope


def bearer_auth_for(*scopes: ApiScope) -> dict[str, str]:
    """Authorization headers for a freshly issued key holding `scopes`.

    Needs the ambient site that `mock_site_context` sets.
    """
    key = ApiKeyFactory(scopes=list(scopes))
    return {"Authorization": f"Bearer {key.issued_key}"}


def query_count(
    client: APIClient, url: str, params: dict[str, str | int], headers: dict[str, str]
) -> int:
    """The number of queries one GET of `url` with `params` runs."""
    with CaptureQueriesContext(connection) as queries:
        client.get(url, params, headers=headers)
    return len(queries)


def api_route_names() -> list[str]:
    """Every URL name the `api` namespace holds."""
    return [pattern.name for pattern in urls.urlpatterns]


def collect_pages(
    client: APIClient, url: str, headers: dict[str, str]
) -> list[dict[str, object]]:
    """The `results` of every page, following `next` until it is null."""
    pages: list[dict[str, object]] = []
    next_url: str | None = url
    while next_url is not None:
        body = client.get(next_url, headers=headers).json()
        pages.append(body)
        next_url = body["next"]
    return pages


class CursorFieldView(APIView):
    """The one attribute the paginator reads from a view."""

    def __init__(self, cursor_field: str) -> None:
        super().__init__()
        self.cursor_field = cursor_field


def paginate_all[M: Model](
    queryset: QuerySet[M],
    path: str = "/pages/",
    cursor_field: str = DEFAULT_CURSOR_FIELD,
) -> list[list[M]]:
    """Every page of `queryset` through `ApiKeysetPagination`, following `next`."""
    factory = APIRequestFactory()
    view = CursorFieldView(cursor_field)
    pages: list[list[M]] = []
    next_url: str | None = path
    while next_url is not None:
        request = Request(factory.get(next_url))
        paginator = ApiKeysetPagination()
        pages.append(paginator.paginate_queryset(queryset, request, view))
        next_url = paginator.get_paginated_response([]).data["next"]
    return pages
