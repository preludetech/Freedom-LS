import pytest

from django.http import QueryDict

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.filters import UpdatedSinceFilterSet
from freedom_ls.api.models import ApiKey

pytestmark = pytest.mark.django_db


class ApiKeyFilterSet(UpdatedSinceFilterSet):
    class Meta:
        model = ApiKey
        fields: list[str] = []


def _filtered(query: str) -> ApiKeyFilterSet:
    return ApiKeyFilterSet(QueryDict(query), queryset=ApiKey._base_manager.all())


def test_updated_since_includes_the_row_at_the_boundary(mock_site_context):
    key = ApiKeyFactory()
    ApiKey._base_manager.filter(pk=key.pk).update(updated_at="2030-01-01T00:00:00Z")

    filterset = _filtered("updated_since=2030-01-01T00:00:00Z")

    assert filterset.is_valid()
    assert [k.pk for k in filterset.qs] == [key.pk]


def test_updated_since_excludes_rows_before_the_boundary(mock_site_context):
    key = ApiKeyFactory()
    ApiKey._base_manager.filter(pk=key.pk).update(updated_at="2030-01-01T00:00:00Z")

    filterset = _filtered("updated_since=2030-01-01T00:00:01Z")

    assert filterset.is_valid()
    assert list(filterset.qs) == []


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("2030-01-01T00:00:00", id="naive"),
        pytest.param("not-a-time", id="unparseable"),
    ],
)
def test_a_naive_or_unparseable_updated_since_is_an_error_on_that_parameter(
    mock_site_context, value
):
    filterset = _filtered(f"updated_since={value}")

    assert not filterset.is_valid()
    assert list(filterset.errors) == ["updated_since"]
