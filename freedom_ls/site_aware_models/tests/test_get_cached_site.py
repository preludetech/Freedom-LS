from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest

from django.contrib.sites.models import Site
from django.test import RequestFactory, override_settings

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.site_aware_models.models import get_cached_site

type AssertNumQueries = Callable[[int], AbstractContextManager[None]]


@pytest.fixture
def request_factory() -> RequestFactory:
    return RequestFactory()


@pytest.mark.django_db
class TestGetCachedSiteWithForceSiteName:
    def test_returns_forced_site_when_matching_site_exists(
        self, request_factory: RequestFactory
    ) -> None:
        forced_site = SiteFactory(name="ForcedSite", domain="forced.example.com")
        request = request_factory.get("/")

        with override_settings(FORCE_SITE_NAME="ForcedSite"):
            result = get_cached_site(request)

        assert result == forced_site

    def test_raises_when_no_matching_site(
        self, request_factory: RequestFactory
    ) -> None:
        SiteFactory(name="TestServer", domain="testserver")
        request = request_factory.get("/")

        with (
            override_settings(FORCE_SITE_NAME="NonExistentSite"),
            pytest.raises(Site.DoesNotExist, match="FORCE_SITE_NAME='NonExistentSite'"),
        ):
            get_cached_site(request)

    def test_uses_get_current_site_when_force_site_name_not_set(
        self, request_factory: RequestFactory
    ) -> None:
        fallback_site = SiteFactory(name="TestServer", domain="testserver")
        request = request_factory.get("/")

        with override_settings(**{"FORCE_SITE_NAME": None}):
            result = get_cached_site(request)

        assert result == fallback_site

    def test_caches_result_on_request(self, request_factory: RequestFactory) -> None:
        forced_site = SiteFactory(name="CachedSite", domain="cached.example.com")
        request = request_factory.get("/")

        with override_settings(FORCE_SITE_NAME="CachedSite"):
            first_result = get_cached_site(request)
            # Second call should use cached value, not hit DB again
            second_result = get_cached_site(request)

        assert first_result == forced_site
        assert second_result == forced_site
        assert first_result is second_result

    def test_cached_value_avoids_extra_db_query(
        self,
        request_factory: RequestFactory,
        django_assert_num_queries: AssertNumQueries,
    ) -> None:
        SiteFactory(name="QueryTestSite", domain="query-test.example.com")
        request = request_factory.get("/")

        with override_settings(FORCE_SITE_NAME="QueryTestSite"):
            # First call hits DB
            get_cached_site(request)
            # Second call should not hit DB
            with django_assert_num_queries(0):
                get_cached_site(request)
