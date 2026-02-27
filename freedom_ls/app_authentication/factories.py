"""Factories for app_authentication models."""

import factory

from freedom_ls.app_authentication.models import Client
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class ClientFactory(SiteAwareFactory):
    """Factory for creating Client instances."""

    class Meta:
        model = Client

    name = factory.Faker("company")
    is_active = True
    # api_key is auto-generated in Client.save(), don't set it here
