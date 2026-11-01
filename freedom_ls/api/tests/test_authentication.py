"""Authentication tests over `APIRequestFactory`.

The cases that need two real `Site` rows and a real `Host` header
(`TestHostMismatch`) take no `mock_site_context`: that fixture pins every host
to one site, which is the thing they check.
"""

from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from django.contrib.sites.models import SITE_CACHE
from django.http import HttpRequest
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from freedom_ls.api.authentication import (
    AUTH_FAILED_MESSAGE,
    ApiKeyAuthentication,
    host_site,
)
from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.models import ApiKey
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


def _authenticate(request: HttpRequest) -> object:
    return ApiKeyAuthentication().authenticate(Request(request))


def _request(
    authorization: str | None = None, path: str = "/api/v1/users/"
) -> HttpRequest:
    extra = {} if authorization is None else {"HTTP_AUTHORIZATION": authorization}
    request: HttpRequest = factory.get(path, **extra)
    return request


def test_no_header_returns_none(mock_site_context):
    assert _authenticate(_request()) is None


def test_a_valid_key_authenticates_with_no_user(mock_site_context):
    api_key = ApiKeyFactory()

    result = _authenticate(_request(f"Bearer {api_key.issued_key}"))

    assert result == (None, api_key)


def test_the_scheme_is_case_insensitive(mock_site_context):
    api_key = ApiKeyFactory()

    result = _authenticate(_request(f"bearer {api_key.issued_key}"))

    assert result == (None, api_key)


def _refused(request: HttpRequest) -> str:
    with pytest.raises(AuthenticationFailed) as exc_info:
        _authenticate(request)
    return str(exc_info.value.detail)


@pytest.mark.parametrize(
    "build_header",
    [
        pytest.param(lambda k: f"Basic {k.issued_key}", id="wrong_scheme"),
        pytest.param(
            lambda k: f"Bearer {k.issued_key.removeprefix('flsk_')}", id="no_prefix"
        ),
        pytest.param(lambda k: f"Bearer flsk_{k.key_prefix}", id="no_dot"),
        pytest.param(lambda k: f"Bearer {k.issued_key} extra", id="extra_part"),
        pytest.param(
            lambda k: "Bearer flsk_0000000000000000.secret", id="unknown_prefix"
        ),
        pytest.param(lambda k: f"Bearer flsk_{k.key_prefix}.wrong", id="wrong_secret"),
    ],
)
def test_a_bad_key_raises_the_one_message(mock_site_context, build_header):
    api_key = ApiKeyFactory()

    assert _refused(_request(build_header(api_key))) == AUTH_FAILED_MESSAGE


def test_a_revoked_key_raises_the_one_message(mock_site_context):
    api_key = ApiKeyFactory()
    api_key.revoke(timezone.now())

    assert _refused(_request(f"Bearer {api_key.issued_key}")) == AUTH_FAILED_MESSAGE


def test_an_expired_key_raises_the_one_message(mock_site_context):
    api_key = ApiKeyFactory()
    ApiKey._base_manager.filter(pk=api_key.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    assert _refused(_request(f"Bearer {api_key.issued_key}")) == AUTH_FAILED_MESSAGE


def test_a_key_in_the_query_string_only_is_not_read(mock_site_context):
    api_key = ApiKeyFactory()

    result = _authenticate(_request(None, f"/api/v1/users/?key={api_key.issued_key}"))

    assert result is None


def test_authenticate_header_names_the_bearer_realm():
    assert (
        ApiKeyAuthentication().authenticate_header(Request(_request()))
        == 'Bearer realm="api"'
    )


def test_host_site_is_none_for_a_host_with_no_row(settings):
    settings.ALLOWED_HOSTS = ["nowhere.example.com"]
    SITE_CACHE.clear()

    assert host_site(factory.get("/", HTTP_HOST="nowhere.example.com")) is None


def test_host_site_is_the_row_for_a_known_host(settings):
    settings.ALLOWED_HOSTS = ["known.example.com"]
    site = SiteFactory(name="Known", domain="known.example.com")
    SITE_CACHE.clear()

    assert host_site(factory.get("/", HTTP_HOST="known.example.com")) == site


class TestHostMismatch:
    @pytest.fixture
    def two_sites(self, settings):
        settings.ALLOWED_HOSTS = ["a.example.com", "b.example.com", "c.example.com"]
        site_a = SiteFactory(name="A", domain="a.example.com")
        site_b = SiteFactory(name="B", domain="b.example.com")
        SITE_CACHE.clear()
        yield site_a, site_b
        SITE_CACHE.clear()

    @pytest.fixture
    def key_of_site_a(self, two_sites):
        with site_context(two_sites[0]):
            return ApiKeyFactory()

    @pytest.mark.parametrize("host", ["b.example.com", "c.example.com"])
    def test_a_key_is_refused_on_another_site_and_on_a_host_with_no_row(
        self, key_of_site_a, host
    ):
        request = factory.get(
            "/api/v1/users/",
            HTTP_HOST=host,
            HTTP_AUTHORIZATION=f"Bearer {key_of_site_a.issued_key}",
        )

        assert _refused(request) == AUTH_FAILED_MESSAGE

    def test_a_key_is_accepted_on_its_own_site(self, key_of_site_a):
        request = factory.get(
            "/api/v1/users/",
            HTTP_HOST="a.example.com",
            HTTP_AUTHORIZATION=f"Bearer {key_of_site_a.issued_key}",
        )

        assert _authenticate(request) == (None, key_of_site_a)


T0 = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _stored(api_key: ApiKey) -> ApiKey:
    return ApiKey._base_manager.get(pk=api_key.pk)


def test_a_successful_authentication_records_last_used_at(mock_site_context):
    with time_machine.travel(T0, tick=False):
        api_key = ApiKeyFactory()
        _authenticate(_request(f"Bearer {api_key.issued_key}"))

    assert _stored(api_key).last_used_at == T0


def test_a_failed_authentication_leaves_last_used_at_empty(mock_site_context):
    api_key = ApiKeyFactory()

    _refused(_request(f"Bearer {api_key.issued_key}x"))

    assert _stored(api_key).last_used_at is None


def test_a_second_use_inside_the_window_leaves_last_used_at(mock_site_context):
    with time_machine.travel(T0, tick=False):
        api_key = ApiKeyFactory()
        _authenticate(_request(f"Bearer {api_key.issued_key}"))
    with time_machine.travel(T0 + timedelta(minutes=4), tick=False):
        _authenticate(_request(f"Bearer {api_key.issued_key}"))

    assert _stored(api_key).last_used_at == T0


def test_a_use_after_the_window_moves_last_used_at(mock_site_context):
    later = T0 + timedelta(minutes=6)
    with time_machine.travel(T0, tick=False):
        api_key = ApiKeyFactory()
        _authenticate(_request(f"Bearer {api_key.issued_key}"))
    with time_machine.travel(later, tick=False):
        _authenticate(_request(f"Bearer {api_key.issued_key}"))

    assert _stored(api_key).last_used_at == later


def test_recording_use_leaves_updated_at_alone(mock_site_context):
    with time_machine.travel(T0, tick=False):
        api_key = ApiKeyFactory()
    updated_at = _stored(api_key).updated_at
    with time_machine.travel(T0 + timedelta(minutes=6), tick=False):
        _authenticate(_request(f"Bearer {api_key.issued_key}"))

    assert _stored(api_key).updated_at == updated_at
