from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import pytest

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.test import RequestFactory, override_settings

from freedom_ls.accounts.factories import (
    SiteFactory,
    SiteSignupPolicyFactory,
    UserFactory,
)
from freedom_ls.site_aware_models.models import (
    SiteResolutionError,
    UnknownSite,
    _thread_locals,
    get_cached_site,
)

type AssertNumQueries = Callable[[int], AbstractContextManager[None]]

# SiteAwareManager: the default queryset only ever sees the current site.
#
# Every site-aware model inherits this manager, so the per-model copies of a
# "rows from another site are filtered out" test all come back to this one
# queryset filter.


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
    """FORCE_SITE_NAME is the only thing that names a tenant without a request.

    Deliberately no ``mock_site_context``: that fixture patches
    ``get_current_site``, which is what let a request-less caller resolve a site
    at all, and so hid this path from the whole suite. ``FORCE_SITE_NAME`` is
    already None for every test.
    """

    def test_a_pinned_install_resolves_without_a_request(self) -> None:
        """The one supported off-request route: an explicitly named tenant."""
        pinned = SiteFactory(name="PinnedTenant", domain="pinned.example.com")

        with override_settings(FORCE_SITE_NAME="PinnedTenant"):
            assert get_cached_site(None) == pinned

    def test_an_unpinned_caller_refuses_rather_than_guessing(self) -> None:
        """Mail carries the tenant's branding, so a wrong guess beats no send.

        Independent of how many Site rows exist: one row is no more an answer
        than two, because the caller still cannot say which tenant it is.
        """
        SiteFactory(name="TenantA", domain="a.example.com")

        with pytest.raises(SiteResolutionError):
            get_cached_site(None)

    def test_the_error_names_the_ways_out_rather_than_site_id(self) -> None:
        """Django's own message points at SITE_ID, the one fix that breaks
        multi-tenancy. This one has to name the two that do not."""
        with pytest.raises(SiteResolutionError) as excinfo:
            get_cached_site(None)

        assert "request" in str(excinfo.value)
        assert "FORCE_SITE_NAME" in str(excinfo.value)


@pytest.mark.django_db
def test_rows_belonging_to_another_site_are_filtered_out(
    mock_site_context: Site,
) -> None:
    here = UserFactory()
    elsewhere = UserFactory(site=Site.objects.create(domain="other.test", name="Other"))

    visible = list(get_user_model().objects.all())

    assert here in visible
    assert elsewhere not in visible


@pytest.mark.django_db
def test_the_base_manager_still_reaches_every_site(mock_site_context: Site) -> None:
    """Site isolation is a default, not a lock: _base_manager crosses sites.

    Admin actions and the report gatherers rely on this, so it is part of the
    contract rather than an accident of Django's manager machinery.
    """
    elsewhere = UserFactory(site=Site.objects.create(domain="other.test", name="Other"))

    assert elsewhere in get_user_model()._base_manager.all()


@contextmanager
def _rejected_host_request() -> Iterator[None]:
    """Put a request whose Host Django already rejected into the thread local.

    `get_cached_site` hands such a request an `UnknownSite`, which is a
    `RequestSite` rather than a row, so it is already cached on the request
    here the way the middleware would have left it.
    """
    request = RequestFactory().get("/")
    request._cached_site = UnknownSite()
    previous = getattr(_thread_locals, "request", None)
    _thread_locals.request = request
    try:
        yield
    finally:
        _thread_locals.request = previous


@pytest.mark.django_db
def test_a_rejected_host_leaves_the_queryset_unfiltered(
    mock_site_context: Site,
) -> None:
    """Filtering on an UnknownSite raises TypeError deep in the ORM, which
    would turn the 400 page Django is rendering for the rejected host into a
    500. The manager falls back to its own default, no site filter at all, the
    way UserManager already does.
    """
    policy = SiteSignupPolicyFactory()

    with _rejected_host_request():
        visible = list(SiteSignupPolicyFactory._meta.model.objects.all())

    assert policy in visible


@pytest.mark.django_db
def test_a_rejected_host_leaves_site_unset_rather_than_assigning_it(
    mock_site_context: Site,
) -> None:
    """Assigning an UnknownSite to the FK raises ValueError from the descriptor,
    long before anything can report which field is missing.
    """
    with _rejected_host_request():
        policy = SiteSignupPolicyFactory._meta.model()

        with pytest.raises(ValidationError) as error:
            policy.full_clean(validate_unique=False, validate_constraints=False)

    assert "site" in error.value.error_dict
