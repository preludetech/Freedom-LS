"""Factories for hr_attributes models."""

import factory

from freedom_ls.hr_attributes.models import (
    Department,
    JobTitle,
    LearnerHRAttributes,
    Location,
    OrganisationHRSettings,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class JobTitleFactory(SiteAwareFactory):
    class Meta:
        model = JobTitle

    organisation = factory.SubFactory(OrganisationFactory)
    name = factory.Sequence(lambda n: f"Job title {n}")
    is_active = True


class DepartmentFactory(SiteAwareFactory):
    class Meta:
        model = Department

    organisation = factory.SubFactory(OrganisationFactory)
    name = factory.Sequence(lambda n: f"Department {n}")
    is_active = True


class LocationFactory(SiteAwareFactory):
    class Meta:
        model = Location

    organisation = factory.SubFactory(OrganisationFactory)
    name = factory.Sequence(lambda n: f"Location {n}")
    is_active = True


class LearnerHRAttributesFactory(SiteAwareFactory):
    """The list entries default into the learner's own organisation.

    Left to build their own, each would land in a different organisation and
    silently persist a row clean() rejects, because factories never call
    full_clean. Pass an explicit entry to build a cross-organisation row on
    purpose, or ``None`` to leave the field empty.
    """

    class Meta:
        model = LearnerHRAttributes

    learner = factory.SubFactory(LearnerFactory)
    job_title = factory.SubFactory(
        JobTitleFactory, organisation=factory.SelfAttribute("..learner.organisation")
    )
    department = factory.SubFactory(
        DepartmentFactory, organisation=factory.SelfAttribute("..learner.organisation")
    )
    location = factory.SubFactory(
        LocationFactory, organisation=factory.SelfAttribute("..learner.organisation")
    )
    organisation_start_date = None
    job_title_start_date = None
    department_start_date = None
    location_start_date = None


class OrganisationHRSettingsFactory(SiteAwareFactory):
    class Meta:
        model = OrganisationHRSettings

    organisation = factory.SubFactory(OrganisationFactory)
    registration_rules_enabled = False
