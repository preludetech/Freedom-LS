from __future__ import annotations

import binascii
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Model, Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import BasePagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from rest_framework.views import APIView

from freedom_ls.site_aware_models.models import TimestampedModel

from .config import config

CURSOR_MAX_LENGTH = 512
BAD_CURSOR = "The cursor is not one this API issued."

M = TypeVar("M", bound=TimestampedModel)


class ApiKeysetPagination(BasePagination):
    ordering = ("updated_at", "id")
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"

    def paginate_queryset(
        self, queryset: QuerySet[M], request: Request, view: APIView | None = None
    ) -> list[M]:
        self.request = request
        self.page_size = self._page_size(request)
        position = self._decode_cursor(request, queryset.model)
        queryset = queryset.order_by(*self.ordering)
        if position is not None:
            updated_at, last_pk = position
            queryset = queryset.filter(
                Q(updated_at__gt=updated_at) | Q(updated_at=updated_at, pk__gt=last_pk)
            )
        # One row past the page says whether a next page exists without a count.
        rows = list(queryset[: self.page_size + 1])
        self.has_next = len(rows) > self.page_size
        self.rows: list[M] = rows[: self.page_size]
        return self.rows

    def get_paginated_response(self, data: list[dict[str, object]]) -> Response:
        return Response({"next": self._next_link(), "results": data})

    def _page_size(self, request: Request) -> int:
        raw = request.query_params.get(self.page_size_query_param)
        if raw is None:
            return config.API_PAGE_SIZE
        try:
            requested = int(raw)
        except ValueError as exc:
            raise ValidationError(
                {self.page_size_query_param: ["Must be a whole number."]}
            ) from exc
        if requested < 1:
            raise ValidationError({self.page_size_query_param: ["Must be at least 1."]})
        return min(requested, config.API_MAX_PAGE_SIZE)

    def _next_link(self) -> str | None:
        if not self.has_next:
            return None
        last = self.rows[-1]
        cursor = self._encode_cursor(last.updated_at, last.pk)
        # replace_query_param keeps every other parameter of the request.
        return str(
            replace_query_param(
                self.request.build_absolute_uri(), self.cursor_query_param, cursor
            )
        )

    def _encode_cursor(self, updated_at: datetime, pk: int | UUID) -> str:
        payload = json.dumps([updated_at.isoformat(), str(pk)])
        return urlsafe_b64encode(payload.encode()).decode()

    def _decode_cursor(
        self, request: Request, model: type[Model]
    ) -> tuple[datetime, int | UUID] | None:
        raw = request.query_params.get(self.cursor_query_param)
        if raw is None:
            return None
        if len(raw) > CURSOR_MAX_LENGTH:
            raise ValidationError({self.cursor_query_param: [BAD_CURSOR]})
        try:
            decoded = json.loads(urlsafe_b64decode(raw.encode()))
            # Exactly two strings: anything else is not a cursor this class wrote.
            if not (
                isinstance(decoded, list)
                and len(decoded) == 2
                and all(isinstance(part, str) for part in decoded)
            ):
                raise ValueError(BAD_CURSOR)
            updated_at = datetime.fromisoformat(decoded[0])
            if timezone.is_naive(updated_at):
                raise ValueError(BAD_CURSOR)
            pk = model._meta.pk.to_python(decoded[1])
        except (
            ValueError,
            TypeError,
            binascii.Error,
            UnicodeDecodeError,
            DjangoValidationError,
        ) as exc:
            raise ValidationError({self.cursor_query_param: [BAD_CURSOR]}) from exc
        return updated_at, pk
