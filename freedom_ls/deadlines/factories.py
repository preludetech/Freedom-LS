"""Factories for deadlines models."""

import factory

from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    DeadlineKind,
    LearnerDeadlineOverride,
)
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_progress.factories import CourseProgressFactory
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
