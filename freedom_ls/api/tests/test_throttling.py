"""The per-key throttle over a stub view."""

import pytest

from django.test import override_settings
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.throttling import ApiKeyRateThrottle

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


class _StubView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []
    throttle_classes = [ApiKeyRateThrottle]

    def get(self, request: Request) -> Response:
        return Response({})


def _get(api_key: object) -> Response:
    request = factory.get("/")
    force_authenticate(request, user=None, token=api_key)
    response: Response = _StubView.as_view()(request)
    return response


def _hit(api_key: object, times: int) -> list[int]:
    return [_get(api_key).status_code for _ in range(times)]


@override_settings(API_THROTTLE_RATE="2/min")
def test_the_third_request_in_the_window_is_429_with_retry_after(mock_site_context):
    api_key = ApiKeyFactory()

    statuses = _hit(api_key, 2)
    response = _get(api_key)

    assert statuses == [200, 200]
    assert response.status_code == 429
    assert int(response["Retry-After"]) > 0


@override_settings(API_THROTTLE_RATE="2/min")
def test_two_keys_count_separately(mock_site_context):
    first = ApiKeyFactory()
    second = ApiKeyFactory()

    _hit(first, 2)

    assert _get(first).status_code == 429
    assert _get(second).status_code == 200


@override_settings(API_THROTTLE_RATE="2/min")
def test_no_key_means_no_cache_key():
    request = Request(factory.get("/"))

    assert ApiKeyRateThrottle().get_cache_key(request, _StubView()) is None


@override_settings(API_THROTTLE_RATE="2/min")
def test_the_cache_key_holds_the_pk_and_not_the_key_text(mock_site_context):
    api_key = ApiKeyFactory()
    request = Request(factory.get("/"))
    request.auth = api_key

    cache_key = ApiKeyRateThrottle().get_cache_key(request, _StubView())

    assert cache_key == f"throttle_api_key_{api_key.pk}"
    assert api_key.issued_key not in cache_key
