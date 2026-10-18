"""Factories for registration_rules models."""

import factory

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.registration_rules.models import RegistrationRule
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class RegistrationRuleFactory(SiteAwareFactory):
    class Meta:
        model = RegistrationRule

    organisation = factory.SubFactory(OrganisationFactory)
    course = factory.SubFactory(CourseFactory)
    name = factory.Sequence(lambda n: f"Registration rule {n}")
    is_enabled = False
