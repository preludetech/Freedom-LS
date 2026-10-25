"""Factories for registration_rules models."""

from collections.abc import Iterable

import factory

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.hr_attributes.models import Department, JobTitle, Location
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.registration_rules.models import (
    AttributeRuleConditions,
    RegistrationRule,
    RuleRecommendation,
    RuleRegistration,
)
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


class RuleRecommendationFactory(SiteAwareFactory):
    class Meta:
        model = RuleRecommendation

    recommendation = factory.SubFactory(RecommendedCourseFactory)
    rule = factory.SubFactory(RegistrationRuleFactory)


class AttributeRuleConditionsFactory(SiteAwareFactory):
    class Meta:
        model = AttributeRuleConditions
        skip_postgeneration_save = True

    rule = factory.SubFactory(RegistrationRuleFactory)

    @factory.post_generation
    def job_titles(self, create: bool, extracted: Iterable[JobTitle] | None) -> None:
        if create and extracted:
            self.job_titles.add(*extracted)

    @factory.post_generation
    def departments(self, create: bool, extracted: Iterable[Department] | None) -> None:
        if create and extracted:
            self.departments.add(*extracted)

    @factory.post_generation
    def locations(self, create: bool, extracted: Iterable[Location] | None) -> None:
        if create and extracted:
            self.locations.add(*extracted)
