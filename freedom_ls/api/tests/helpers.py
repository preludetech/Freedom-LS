"""Helpers shared by the API tests, here and in the apps that register endpoints."""

from __future__ import annotations

from django.db.models import QuerySet
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from freedom_ls.api import urls
from freedom_ls.api.pagination import ApiKeysetPagination
from freedom_ls.site_aware_models.models import TimestampedModel


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


def paginate_all[M: TimestampedModel](
    queryset: QuerySet[M], path: str = "/pages/"
) -> list[list[M]]:
    """Every page of `queryset` through `ApiKeysetPagination`, following `next`."""
    factory = APIRequestFactory()
    pages: list[list[M]] = []
    next_url: str | None = path
    while next_url is not None:
        request = Request(factory.get(next_url))
        paginator = ApiKeysetPagination()
        pages.append(paginator.paginate_queryset(queryset, request))
        next_url = paginator.get_paginated_response([]).data["next"]
    return pages
