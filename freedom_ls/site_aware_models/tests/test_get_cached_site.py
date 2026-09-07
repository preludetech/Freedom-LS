from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest

from django.contrib.sites.models import Site
from django.test import RequestFactory, override_settings

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.models import (
    SiteResolutionError,
    get_cached_site,
)

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


@pytest.mark.django_db
class TestGetCachedSiteWithoutARequest:
    """Outbound mail is not always sent from a request, and FLS pins no SITE_ID.

    Deliberately no ``mock_site_context``: that fixture patches the very
    ``get_current_site`` call these tests exercise, which is why the suite
    never caught this. ``FORCE_SITE_NAME`` is already None for every test.

    Django's own sites migration seeds one ``example.com`` row, so the row
    count is set explicitly rather than assumed.
    """

    def test_a_single_site_install_resolves_without_a_request(self) -> None:
        """One Site is one answer, so a request-less caller gets it.

        The seeded row is the whole population here, which is the shape of a
        fresh single-tenant install -- it is not deleted and replaced because
        the same migration hangs a protected Organisation off it.
        """
        only_site = Site.objects.get()

        assert get_cached_site(None) == only_site

    def test_two_sites_refuse_to_guess(self) -> None:
        """Guessing here would brand a password reset with the wrong tenant."""
        SiteFactory(name="TenantA", domain="a.example.com")
        SiteFactory(name="TenantB", domain="b.example.com")

        with pytest.raises(SiteResolutionError, match="FORCE_SITE_NAME"):
            get_cached_site(None)

    def test_no_sites_at_all_is_an_error_too(self) -> None:
        """Guards the lower edge of the "exactly one" rule."""
        # The seeded Organisation holds a protected FK to the seeded Site, so
        # it has to go first for the Site to be deletable at all.
        Organisation._base_manager.all().delete()
        Site.objects.all().delete()

        with pytest.raises(SiteResolutionError):
            get_cached_site(None)

    def test_the_error_names_the_ways_out_rather_than_site_id_alone(self) -> None:
        """Django's own message points at SITE_ID, the one fix that breaks
        multi-tenancy. This one has to name passing the request instead."""
        SiteFactory(name="TenantA", domain="a.example.com")
        SiteFactory(name="TenantB", domain="b.example.com")

        with pytest.raises(SiteResolutionError) as excinfo:
            get_cached_site(None)

        assert "request" in str(excinfo.value)
        assert "FORCE_SITE_NAME" in str(excinfo.value)
