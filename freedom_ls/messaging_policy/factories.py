from __future__ import annotations

import factory

from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.messaging_policy.models import (
    CohortMessagingConfig,
    OrganisationMessagingConfig,
    SiteMessagingConfig,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class SiteMessagingConfigFactory(SiteAwareFactory):
    class Meta:
        model = SiteMessagingConfig


class OrganisationMessagingConfigFactory(SiteAwareFactory):
    class Meta:
        model = OrganisationMessagingConfig

    organisation = factory.SubFactory(OrganisationFactory)


class CohortMessagingConfigFactory(SiteAwareFactory):
    class Meta:
        model = CohortMessagingConfig

    cohort = factory.SubFactory(CohortFactory)
