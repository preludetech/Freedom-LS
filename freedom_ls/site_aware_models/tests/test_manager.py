"""SiteAwareManager: the default queryset only ever sees the current site.

Every site-aware model inherits this manager, so the per-model copies of a
"rows from another site are filtered out" test all come back to this one
queryset filter.
"""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User

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
