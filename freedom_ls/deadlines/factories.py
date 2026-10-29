"""Factories for deadlines models."""

import factory

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.deadlines.models import (
    CohortCourseRegistrationDeadlineConfig,
    CohortDeadlineConfig,
    CohortDeadlineOverride,
    CourseDeadlineConfig,
    DeadlineKind,
    LearnerCourseRegistrationDeadlineConfig,
    LearnerDeadlineOverride,
    OrganisationDeadlineConfig,
    SiteDeadlineConfig,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class CohortDeadlineOverrideFactory(SiteAwareFactory):
    """A time-limit override (no collection item) of 14 days after registration.

    Pass ``collection_item=...`` to override one item of the registration's course.
    """

    class Meta:
        model = CohortDeadlineOverride

    cohort_registration = factory.SubFactory(CohortCourseRegistrationFactory)
    collection_item = None
    kind = DeadlineKind.RELATIVE
    due_days_after_registration = 14


class LearnerDeadlineOverrideFactory(SiteAwareFactory):
    """A time-limit override (no collection item) of 14 days after registration.

    Pass ``collection_item=...`` to override one item of the record's course.
    """

    class Meta:
        model = LearnerDeadlineOverride

    course_progress = factory.SubFactory(CourseProgressFactory)
    collection_item = None
    kind = DeadlineKind.RELATIVE
    due_days_after_registration = 14


class SiteDeadlineConfigFactory(SiteAwareFactory):
    """A site config row with every setting left to inherit."""

    class Meta:
        model = SiteDeadlineConfig


class OrganisationDeadlineConfigFactory(SiteAwareFactory):
    class Meta:
        model = OrganisationDeadlineConfig

    organisation = factory.SubFactory(OrganisationFactory)


class CourseDeadlineConfigFactory(SiteAwareFactory):
    class Meta:
        model = CourseDeadlineConfig

    course = factory.SubFactory(CourseFactory)


class CohortDeadlineConfigFactory(SiteAwareFactory):
    class Meta:
        model = CohortDeadlineConfig

    cohort = factory.SubFactory(CohortFactory)


class CohortCourseRegistrationDeadlineConfigFactory(SiteAwareFactory):
    class Meta:
        model = CohortCourseRegistrationDeadlineConfig

    cohort_registration = factory.SubFactory(CohortCourseRegistrationFactory)


class LearnerCourseRegistrationDeadlineConfigFactory(SiteAwareFactory):
    class Meta:
        model = LearnerCourseRegistrationDeadlineConfig

    learner_registration = factory.SubFactory(LearnerCourseRegistrationFactory)
