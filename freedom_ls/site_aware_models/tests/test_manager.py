"""SiteAwareManager: the default queryset only ever sees the current site.

Every site-aware model inherits this manager, so the per-model copies of a
"rows from another site are filtered out" test all come back to this one
queryset filter.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.models import SiteSignupPolicy, User
from freedom_ls.site_aware_models.models import UnknownSite, _thread_locals

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.django_db


def test_rows_belonging_to_another_site_are_filtered_out(
    mock_site_context: Site,
) -> None:
    here = UserFactory()
    elsewhere = UserFactory(site=Site.objects.create(domain="other.test", name="Other"))

    visible = list(User.objects.all())

    assert here in visible
    assert elsewhere not in visible


def test_the_base_manager_still_reaches_every_site(mock_site_context: Site) -> None:
    """Site isolation is a default, not a lock: _base_manager crosses sites.

    Admin actions and the report gatherers rely on this, so it is part of the
    contract rather than an accident of Django's manager machinery.
    """
    elsewhere = UserFactory(site=Site.objects.create(domain="other.test", name="Other"))

    assert elsewhere in User._base_manager.all()


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
        visible = list(SiteSignupPolicy.objects.all())

    assert policy in visible


def test_a_rejected_host_leaves_site_unset_rather_than_assigning_it(
    mock_site_context: Site,
) -> None:
    """Assigning an UnknownSite to the FK raises ValueError from the descriptor,
    long before anything can report which field is missing.
    """
    with _rejected_host_request():
        policy = SiteSignupPolicy()

        with pytest.raises(ValidationError) as error:
            policy.full_clean(validate_unique=False, validate_constraints=False)

    assert "site" in error.value.error_dict
