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


class ListEntryFactory(SiteAwareFactory):
    class Meta:
        abstract = True

    organisation = factory.SubFactory(OrganisationFactory)
    is_active = True


class JobTitleFactory(ListEntryFactory):
    class Meta:
        model = JobTitle

    name = factory.Sequence(lambda n: f"Job title {n}")


class DepartmentFactory(ListEntryFactory):
    class Meta:
        model = Department

    name = factory.Sequence(lambda n: f"Department {n}")


class LocationFactory(ListEntryFactory):
    class Meta:
        model = Location

    name = factory.Sequence(lambda n: f"Location {n}")


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
