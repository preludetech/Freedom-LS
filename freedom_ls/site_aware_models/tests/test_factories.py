"""Tests for site_aware_models factories."""

import factory
import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class ConcreteUserFactory(SiteAwareFactory):
    """Concrete factory for testing SiteAwareFactory with the User model."""

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"sitetest{n}@example.com")
    is_active = True


@pytest.mark.django_db
class TestSiteAwareFactory:
    def test_picks_up_site_from_mock_site_context(self, mock_site_context: Site) -> None:
        """SiteAwareFactory subclass should automatically get site from thread-local context."""
        user = ConcreteUserFactory()
        assert user.site == mock_site_context

    def test_site_can_be_overridden_explicitly(self, mock_site_context: Site) -> None:
        """Site can be explicitly overridden when creating an object."""
        other_site = Site.objects.create(domain="other.example.com", name="Other Site")
        user = ConcreteUserFactory(site=other_site)
        assert user.site == other_site
        assert user.site != mock_site_context
