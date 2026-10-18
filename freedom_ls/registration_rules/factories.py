"""Factories for registration_rules models."""

import factory

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class RegistrationRuleFactory(SiteAwareFactory):
    class Meta:
        model = RegistrationRule

    organisation = factory.SubFactory(OrganisationFactory)
    course = factory.SubFactory(CourseFactory)
    name = factory.Sequence(lambda n: f"Registration rule {n}")
    is_enabled = False


class RuleRegistrationFactory(SiteAwareFactory):
    class Meta:
        model = RuleRegistration

    registration = factory.SubFactory(LearnerCourseRegistrationFactory)
    rule = factory.SubFactory(RegistrationRuleFactory)
    rule_name = factory.LazyAttribute(lambda o: o.rule.name)
    is_retracted = False
