from __future__ import annotations

import binascii
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Callable
from datetime import date, datetime
from typing import TypeVar
from uuid import UUID

from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Model, Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import BasePagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from rest_framework.views import APIView

from .config import config

CURSOR_MAX_LENGTH = 512
BAD_CURSOR = "The cursor is not one this API issued."

M = TypeVar("M", bound=Model)

DEFAULT_CURSOR_FIELD = "updated_at"


def _parse_aware_datetime(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    # A naive instant has no single position on an aware column.
    if timezone.is_naive(parsed):
        raise ValueError(BAD_CURSOR)
    return parsed


# Keyed by get_internal_type, not matched with isinstance: DateTimeField
# subclasses DateField, so an isinstance chain would have to be ordered by hand.
_CURSOR_PARSERS: dict[str, Callable[[str], date]] = {
    "DateTimeField": _parse_aware_datetime,
}


def _cursor_parser(model: type[Model], cursor_field: str) -> Callable[[str], date]:
    """The parser for the cursor field's type."""
    field = model._meta.get_field(cursor_field)
    parse = _CURSOR_PARSERS.get(field.get_internal_type())
    if parse is None:
        raise ImproperlyConfigured(
            f"{model.__name__}.{cursor_field} is not a field this pagination can page on."
        )
    return parse


class ApiKeysetPagination(BasePagination):
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"

    def paginate_queryset(
        self, queryset: QuerySet[M], request: Request, view: APIView | None = None
    ) -> list[M]:
        self.request = request
        # Bound to a str name first: rest_framework is untyped, so the
        # attribute arrives as Any.
        cursor_field: str = getattr(view, "cursor_field", DEFAULT_CURSOR_FIELD)
        self.cursor_field = cursor_field
        # Resolved before the cursor is read, so a viewset paging on a field
        # of the wrong type fails on its first page, not on its second.
        parse = _cursor_parser(queryset.model, cursor_field)
        self.page_size = self._page_size(request)
        position = self._decode_cursor(request, queryset.model, parse)
        queryset = queryset.order_by(cursor_field, "id")
        if position is not None:
            value, last_pk = position
            queryset = queryset.filter(
                Q(**{f"{cursor_field}__gt": value})
                | Q(**{cursor_field: value, "pk__gt": last_pk})
            )
        # One row past the page says whether a next page exists without a count.
        rows = list(queryset[: self.page_size + 1])
        self.has_next = len(rows) > self.page_size
        self.rows: list[M] = rows[: self.page_size]
        return self.rows

    def get_paginated_response(self, data: list[dict[str, object]]) -> Response:
        return Response({"next": self._next_link(), "results": data})

    def get_schema_operation_parameters(self, view: APIView) -> list[dict[str, object]]:
        return [
            {
                "name": self.cursor_query_param,
                "required": False,
                "in": "query",
                "description": "Opaque position token taken from the previous page's next link.",
                "schema": {"type": "string"},
            },
            {
                "name": self.page_size_query_param,
                "required": False,
                "in": "query",
                "description": "Number of results per page.",
                "schema": {
                    "type": "integer",
                    "default": config.API_PAGE_SIZE,
                    "maximum": config.API_MAX_PAGE_SIZE,
                    "minimum": 1,
                },
            },
        ]

    def get_paginated_response_schema(
        self, schema: dict[str, object]
    ) -> dict[str, object]:
        return {
            "type": "object",
            "required": ["next", "results"],
            "properties": {
                "next": {"type": "string", "nullable": True, "format": "uri"},
                "results": schema,
            },
        }

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
        cursor = self._encode_cursor(getattr(last, self.cursor_field), last.pk)
        # replace_query_param keeps every other parameter of the request.
        return str(
            replace_query_param(
                self.request.build_absolute_uri(), self.cursor_query_param, cursor
            )
        )

    def _encode_cursor(self, value: date, pk: int | UUID) -> str:
        # datetime is a date, so one signature covers both cursor field types.
        payload = json.dumps([value.isoformat(), str(pk)])
        return urlsafe_b64encode(payload.encode()).decode()

    def _decode_cursor(
        self, request: Request, model: type[Model], parse: Callable[[str], date]
    ) -> tuple[date, int | UUID] | None:
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
            value = parse(decoded[0])
            pk = model._meta.pk.to_python(decoded[1])
        except (
            ValueError,
            TypeError,
            binascii.Error,
            UnicodeDecodeError,
            DjangoValidationError,
        ) as exc:
            raise ValidationError({self.cursor_query_param: [BAD_CURSOR]}) from exc
        return value, pk
