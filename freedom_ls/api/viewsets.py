from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.openapi import AutoSchema

from django.db.models import Model, QuerySet
from django.utils.cache import patch_cache_control
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from .authentication import ApiKeyAuthentication
from .exceptions import api_exception_handler
from .metadata import ApiMetadata
from .models import ApiKey
from .pagination import ApiKeysetPagination
from .permissions import HasApiScope
from .scopes import ApiScope
from .throttling import ApiKeyRateThrottle

M = TypeVar("M", bound=Model)


class ApiResponseMixin(APIView):
    """The error body and cache headers every API response shares."""

    def get_exception_handler(
        self,
    ) -> Callable[[Exception, dict[str, object]], Response | None]:
        return api_exception_handler

    def finalize_response(
        self, request: Request, response: Response, *args: object, **kwargs: object
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        # Every body is one site's personal data: no shared cache may keep it.
        patch_cache_control(response, private=True, no_store=True)
        return response


class ReadOnlyApiViewSet(ApiResponseMixin, ReadOnlyModelViewSet):
    required_scope: ApiScope

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    renderer_classes = [JSONRenderer]
    pagination_class = ApiKeysetPagination
    filter_backends = [DjangoFilterBackend]
    metadata_class = ApiMetadata
    http_method_names = ["get", "head", "options"]
    schema = AutoSchema()

    def site_queryset(self, queryset: QuerySet[M]) -> QuerySet[M]:
        """Rows of the authenticated key's site, and nothing when there is no key.

        Schema generation and any request that got past authentication without
        a key must see an empty queryset rather than the host-filtered manager's.
        """
        api_key = self.request.auth
        if getattr(self, "swagger_fake_view", False) or not isinstance(api_key, ApiKey):
            return queryset.none()
        return queryset.filter(site=api_key.site)
