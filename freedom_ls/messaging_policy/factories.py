from __future__ import annotations

import factory

from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.messaging_policy.models import (
    CohortCourseRegistrationMessagingConfig,
    CohortMessagingConfig,
    LearnerCourseRegistrationMessagingConfig,
    LearnerMessagingConfig,
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


class LearnerMessagingConfigFactory(SiteAwareFactory):
    class Meta:
        model = LearnerMessagingConfig

    learner = factory.SubFactory(LearnerFactory)


class LearnerCourseRegistrationMessagingConfigFactory(SiteAwareFactory):
    class Meta:
        model = LearnerCourseRegistrationMessagingConfig

    registration = factory.SubFactory(LearnerCourseRegistrationFactory)


class CohortCourseRegistrationMessagingConfigFactory(SiteAwareFactory):
    class Meta:
        model = CohortCourseRegistrationMessagingConfig

    registration = factory.SubFactory(CohortCourseRegistrationFactory)
