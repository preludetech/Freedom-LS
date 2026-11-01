import json
from base64 import urlsafe_b64encode
from datetime import UTC, datetime

import pytest

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.models import ApiKey
from freedom_ls.api.pagination import (
    BAD_CURSOR,
    CURSOR_MAX_LENGTH,
    ApiKeysetPagination,
)
from freedom_ls.api.tests.helpers import paginate_all

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


@pytest.fixture
def small_pages(settings):
    settings.API_PAGE_SIZE = 2


def _cursor(payload: object) -> str:
    return urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _paginate_with_cursor(cursor: str) -> None:
    request = Request(factory.get("/pages/", {"cursor": cursor}))
    ApiKeysetPagination().paginate_queryset(ApiKey._base_manager.all(), request)


def test_every_row_is_returned_once_and_the_last_page_has_no_next(
    mock_site_context, small_pages
):
    keys = [ApiKeyFactory() for _ in range(5)]

    pages = paginate_all(ApiKey._base_manager.all())

    assert sorted(k.pk for page in pages for k in page) == sorted(k.pk for k in keys)
    assert [len(page) for page in pages] == [2, 2, 1]


def test_the_next_link_keeps_the_other_query_parameters(mock_site_context, small_pages):
    [ApiKeyFactory() for _ in range(3)]
    request = Request(factory.get("/pages/", {"flag": "yes"}))
    paginator = ApiKeysetPagination()
    paginator.paginate_queryset(ApiKey._base_manager.all(), request)

    next_link = paginator.get_paginated_response([]).data["next"]

    assert "flag=yes" in next_link
    assert "cursor=" in next_link


def test_a_tie_group_larger_than_a_page_has_no_duplicates_or_skips(
    mock_site_context, small_pages
):
    keys = [ApiKeyFactory() for _ in range(5)]
    ApiKey._base_manager.update(updated_at=datetime(2030, 1, 1, tzinfo=UTC))

    pages = paginate_all(ApiKey._base_manager.all())

    seen = [k.pk for page in pages for k in page]
    assert sorted(seen) == sorted(k.pk for k in keys)
    assert len(seen) == 5


@pytest.mark.parametrize(
    "cursor",
    [
        pytest.param(
            _cursor(["2030-01-01T00:00:00+00:00", "not-a-uuid"]), id="pk_not_a_uuid"
        ),
        pytest.param(
            _cursor(
                [
                    "2030-01-01T00:00:00+00:00",
                    "00000000-0000-0000-0000-000000000000",
                    "x",
                ]
            ),
            id="three_elements",
        ),
        pytest.param(_cursor({"a": "b"}), id="object"),
        pytest.param(
            _cursor(["2030-01-01T00:00:00", "00000000-0000-0000-0000-000000000000"]),
            id="naive_timestamp",
        ),
        pytest.param("x" * (CURSOR_MAX_LENGTH + 1), id="too_long"),
        pytest.param("!!!not base64!!!", id="not_base64"),
    ],
)
def test_a_cursor_the_api_did_not_issue_is_a_400(mock_site_context, cursor):
    with pytest.raises(ValidationError) as exc_info:
        _paginate_with_cursor(cursor)

    assert exc_info.value.detail == {"cursor": [BAD_CURSOR]}


def test_a_page_size_above_the_cap_is_clamped(mock_site_context, settings):
    settings.API_MAX_PAGE_SIZE = 3
    [ApiKeyFactory() for _ in range(5)]

    pages = paginate_all(ApiKey._base_manager.all(), "/pages/?page_size=100")

    assert [len(page) for page in pages] == [3, 2]


def test_a_page_size_within_the_cap_is_used(mock_site_context):
    [ApiKeyFactory() for _ in range(5)]

    pages = paginate_all(ApiKey._base_manager.all(), "/pages/?page_size=2")

    assert [len(page) for page in pages] == [2, 2, 1]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        pytest.param("0", "Must be at least 1.", id="zero"),
        pytest.param("-4", "Must be at least 1.", id="negative"),
        pytest.param("x", "Must be a whole number.", id="not_a_number"),
    ],
)
def test_an_invalid_page_size_is_a_400(mock_site_context, value, message):
    request = Request(factory.get("/pages/", {"page_size": value}))

    with pytest.raises(ValidationError) as exc_info:
        ApiKeysetPagination().paginate_queryset(ApiKey._base_manager.all(), request)

    assert exc_info.value.detail == {"page_size": [message]}


def test_the_next_link_keeps_updated_since_and_page_size(mock_site_context):
    [ApiKeyFactory() for _ in range(3)]
    request = Request(
        factory.get(
            "/pages/", {"updated_since": "2020-01-01T00:00:00Z", "page_size": "2"}
        )
    )
    paginator = ApiKeysetPagination()
    paginator.paginate_queryset(ApiKey._base_manager.all(), request)

    next_link = paginator.get_paginated_response([]).data["next"]

    assert "updated_since=2020-01-01T00%3A00%3A00Z" in next_link
    assert "page_size=2" in next_link


def test_schema_parameters_describe_cursor_and_page_size(settings):
    settings.API_PAGE_SIZE = 7
    settings.API_MAX_PAGE_SIZE = 70

    cursor, page_size = ApiKeysetPagination().get_schema_operation_parameters(APIView())

    assert cursor == {
        "name": "cursor",
        "required": False,
        "in": "query",
        "description": "Opaque position token taken from the previous page's next link.",
        "schema": {"type": "string"},
    }
    assert page_size["name"] == "page_size"
    assert page_size["schema"] == {
        "type": "integer",
        "default": 7,
        "maximum": 70,
        "minimum": 1,
    }


def test_paginated_response_schema_has_next_and_results():
    items = {"type": "array", "items": {"type": "object"}}

    schema = ApiKeysetPagination().get_paginated_response_schema(items)

    assert schema["properties"] == {
        "next": {"type": "string", "nullable": True, "format": "uri"},
        "results": items,
    }
