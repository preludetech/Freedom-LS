"""Factories for student_management models."""

from datetime import timedelta

import factory

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.site_aware_models.factories import SiteAwareFactory
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    RecommendedCourse,
    Student,
    StudentCohortDeadlineOverride,
    StudentCourseRegistration,
    StudentDeadline,
)


class StudentFactory(SiteAwareFactory):
    """Factory for creating Student instances."""

    class Meta:
        model = Student

    user = factory.SubFactory(UserFactory)


class CohortFactory(SiteAwareFactory):
    """Factory for creating Cohort instances."""

    class Meta:
        model = Cohort

    name = factory.Sequence(lambda n: f"Cohort {n}")


class CohortMembershipFactory(SiteAwareFactory):
    """Factory for creating CohortMembership instances."""

    class Meta:
        model = CohortMembership

    student = factory.SubFactory(StudentFactory)
    cohort = factory.SubFactory(CohortFactory)


class StudentCourseRegistrationFactory(SiteAwareFactory):
    """Factory for creating StudentCourseRegistration instances."""

    class Meta:
        model = StudentCourseRegistration

    student = factory.SubFactory(StudentFactory)
    collection = factory.SubFactory(CourseFactory)
    is_active = True


class CohortCourseRegistrationFactory(SiteAwareFactory):
    """Factory for creating CohortCourseRegistration instances."""

    class Meta:
        model = CohortCourseRegistration

    cohort = factory.SubFactory(CohortFactory)
    collection = factory.SubFactory(CourseFactory)
    is_active = True


class CohortDeadlineFactory(SiteAwareFactory):
    """Factory for creating CohortDeadline instances.

    Pass ``content_item=<model instance>`` to set the GenericFK fields.
    When omitted, content_type and object_id default to None (course-level deadline).
    """

    class Meta:
        model = CohortDeadline
        exclude = ["content_item"]

    class Params:
        content_item = None

    cohort_course_registration = factory.SubFactory(CohortCourseRegistrationFactory)
    deadline = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    is_hard_deadline = False

    content_type = factory.LazyAttribute(
        lambda obj: ContentType.objects.get_for_model(obj.content_item)
        if obj.content_item
        else None
    )
    object_id = factory.LazyAttribute(
        lambda obj: obj.content_item.pk if obj.content_item else None
    )


class StudentDeadlineFactory(SiteAwareFactory):
    """Factory for creating StudentDeadline instances.

    Pass ``content_item=<model instance>`` to set the GenericFK fields.
    When omitted, content_type and object_id default to None (course-level deadline).
    """

    class Meta:
        model = StudentDeadline
        exclude = ["content_item"]

    class Params:
        content_item = None

    student_course_registration = factory.SubFactory(
        StudentCourseRegistrationFactory
    )
    deadline = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    is_hard_deadline = False

    content_type = factory.LazyAttribute(
        lambda obj: ContentType.objects.get_for_model(obj.content_item)
        if obj.content_item
        else None
    )
    object_id = factory.LazyAttribute(
        lambda obj: obj.content_item.pk if obj.content_item else None
    )


class StudentCohortDeadlineOverrideFactory(SiteAwareFactory):
    """Factory for creating StudentCohortDeadlineOverride instances.

    Pass ``content_item=<model instance>`` to set the GenericFK fields.
    When omitted, content_type and object_id default to None (course-level override).
    """

    class Meta:
        model = StudentCohortDeadlineOverride
        exclude = ["content_item"]

    class Params:
        content_item = None

    cohort_course_registration = factory.SubFactory(CohortCourseRegistrationFactory)
    student = factory.SubFactory(StudentFactory)
    deadline = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    is_hard_deadline = False

    content_type = factory.LazyAttribute(
        lambda obj: ContentType.objects.get_for_model(obj.content_item)
        if obj.content_item
        else None
    )
    object_id = factory.LazyAttribute(
        lambda obj: obj.content_item.pk if obj.content_item else None
    )


class RecommendedCourseFactory(SiteAwareFactory):
    """Factory for creating RecommendedCourse instances."""

    class Meta:
        model = RecommendedCourse

    user = factory.SubFactory(UserFactory)
    collection = factory.SubFactory(CourseFactory)
