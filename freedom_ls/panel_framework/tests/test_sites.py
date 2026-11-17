"""How a request's site is resolved: the default, the setting, per-request
caching and the errors a bad setting raises."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from pytest_django.fixtures import SettingsWrapper

from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.test import RequestFactory, override_settings

from freedom_ls.panel_framework.sites import resolve_site

from .helpers import make_site

pytestmark = pytest.mark.django_db

CALLS: list[HttpRequest] = []
NOT_CALLABLE = "a string, not a callable"
NOT_CALLABLE_PATH = f"{__name__}.NOT_CALLABLE"


class ResolverError(Exception):
    """Raised by a stand-in resolver to prove other exceptions propagate."""


def returns_site(request: HttpRequest) -> Site:
    CALLS.append(request)
    return Site(id=999, name="Stand-in", domain="stand-in.test")


def returns_request_site(request: HttpRequest) -> RequestSite:
    CALLS.append(request)
    return RequestSite(request)


def raises_does_not_exist(request: HttpRequest) -> Site:
    CALLS.append(request)
    raise Site.DoesNotExist


def raises_failure(request: HttpRequest) -> Site:
    raise ResolverError


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    # get_current_site caches by host for the life of the process.
    Site.objects.clear_cache()
    CALLS.clear()
    yield
    Site.objects.clear_cache()
    CALLS.clear()


@pytest.fixture
def default_resolver(settings: SettingsWrapper) -> None:
    """Drop the project's resolver so the framework's declared default applies."""
    del settings.PANEL_FRAMEWORK_SITE_RESOLVER


def _request(host: str = "testserver") -> HttpRequest:
    return RequestFactory().get("/", HTTP_HOST=host)


def _path(function: Callable[..., object]) -> str:
    return f"{__name__}.{function.__name__}"


@override_settings(SITE_ID=None, ALLOWED_HOSTS=["*"])
@pytest.mark.usefixtures("default_resolver")
def test_default_resolver_returns_the_site_whose_domain_is_the_requests_host() -> None:
    make_site("Other", "other.test")
    wanted = make_site("Wanted", "wanted.test")

    assert resolve_site(_request("wanted.test")) == wanted


@override_settings(SITE_ID=None, ALLOWED_HOSTS=["*"])
@pytest.mark.usefixtures("default_resolver")
def test_default_resolver_returns_none_for_a_host_matching_no_site() -> None:
    make_site("Other", "other.test")

    assert resolve_site(_request("unknown.test")) is None


def test_the_setting_overrides_the_default_resolver() -> None:
    with override_settings(PANEL_FRAMEWORK_SITE_RESOLVER=_path(returns_site)):
        site = resolve_site(_request())

    assert site is not None
    assert site.domain == "stand-in.test"


@pytest.mark.parametrize(
    "resolver", [returns_site, returns_request_site, raises_does_not_exist]
)
def test_the_resolver_runs_once_per_request(resolver: Callable[..., object]) -> None:
    first, second = _request(), _request()

    with override_settings(PANEL_FRAMEWORK_SITE_RESOLVER=_path(resolver)):
        resolve_site(first)
        resolve_site(first)
        assert len(CALLS) == 1
        resolve_site(second)

    assert len(CALLS) == 2


def test_a_request_site_result_resolves_to_none() -> None:
    with override_settings(PANEL_FRAMEWORK_SITE_RESOLVER=_path(returns_request_site)):
        assert resolve_site(_request()) is None


def test_a_resolver_raising_any_other_exception_propagates_it() -> None:
    with (
        override_settings(PANEL_FRAMEWORK_SITE_RESOLVER=_path(raises_failure)),
        pytest.raises(ResolverError),
    ):
        resolve_site(_request())


@pytest.mark.parametrize(
    "bad_value",
    ["no.such.module.resolver", NOT_CALLABLE_PATH, 42],
)
def test_a_bad_setting_raises_improperly_configured_naming_setting_and_value(
    bad_value: object,
) -> None:
    with (
        override_settings(PANEL_FRAMEWORK_SITE_RESOLVER=bad_value),
        pytest.raises(ImproperlyConfigured) as raised,
    ):
        resolve_site(_request())

    message = str(raised.value)
    assert "PANEL_FRAMEWORK_SITE_RESOLVER" in message
    assert repr(bad_value) in message
