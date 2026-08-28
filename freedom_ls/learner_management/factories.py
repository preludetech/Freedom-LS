"""Factories for learner_management models."""

from datetime import timedelta
from typing import cast

import factory

from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    Learner,
    LearnerCohortDeadlineOverride,
    LearnerCourseRegistration,
    LearnerDeadline,
    RecommendedCourse,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class LearnerFactory(SiteAwareFactory):
    """Factory for creating Learner instances.

    Delegates to ensure_learner so that repeated calls with the same
    user/organisation return the existing row rather than violating
    unique_learner_per_organisation. ensure_learner always reactivates, so
    ``is_active=False`` is applied afterwards to build a removed learner.
    """

    class Meta:
        model = Learner

    user = factory.SubFactory(UserFactory)
    organisation = factory.SubFactory(OrganisationFactory)
    is_active = True

    @classmethod
    def _create(
        cls,
        model_class: type[django_models.Model],
        *args: object,
        **kwargs: object,
    ) -> django_models.Model:
        learner = ensure_learner(
            cast(User, kwargs["user"]), cast(Organisation, kwargs["organisation"])
        )
        if not kwargs.get("is_active", True):
            learner.is_active = False
            learner.save(update_fields=["is_active"])
        return learner


class CohortFactory(SiteAwareFactory):
    """Factory for creating Cohort instances."""

    class Meta:
        model = Cohort

    organisation = factory.SubFactory(OrganisationFactory)
    name = factory.Sequence(lambda n: f"Cohort {n}")


class CohortMembershipFactory(SiteAwareFactory):
    """Factory for creating CohortMembership instances.

    The learner defaults into the cohort's own organisation. Left to build its
    own, it would land in a third organisation and silently persist a row that
    CohortMembership.clean() rejects -- factories never call full_clean. Pass
    an explicit ``learner`` to build a cross-organisation row deliberately.
    """

    class Meta:
        model = CohortMembership

    learner = factory.SubFactory(
        LearnerFactory, organisation=factory.SelfAttribute("..cohort.organisation")
    )
    cohort = factory.SubFactory(CohortFactory)


class LearnerCourseRegistrationFactory(SiteAwareFactory):
    """Factory for creating LearnerCourseRegistration instances."""

    class Meta:
        model = LearnerCourseRegistration

    learner = factory.SubFactory(LearnerFactory)
    course = factory.SubFactory(CourseFactory)
    is_active = True


class CohortCourseRegistrationFactory(SiteAwareFactory):
    """Factory for creating CohortCourseRegistration instances."""

    class Meta:
        model = CohortCourseRegistration

    cohort = factory.SubFactory(CohortFactory)
    course = factory.SubFactory(CourseFactory)
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
        lambda obj: (
            ContentType.objects.get_for_model(obj.content_item)
            if obj.content_item
            else None
        )
    )
    object_id = factory.LazyAttribute(
        lambda obj: obj.content_item.pk if obj.content_item else None
    )


class LearnerDeadlineFactory(SiteAwareFactory):
    """Factory for creating LearnerDeadline instances.

    Pass ``content_item=<model instance>`` to set the GenericFK fields.
    When omitted, content_type and object_id default to None (course-level deadline).
    """

    class Meta:
        model = LearnerDeadline
        exclude = ["content_item"]

    class Params:
        content_item = None

    learner_course_registration = factory.SubFactory(LearnerCourseRegistrationFactory)
    deadline = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    is_hard_deadline = False

    content_type = factory.LazyAttribute(
        lambda obj: (
            ContentType.objects.get_for_model(obj.content_item)
            if obj.content_item
            else None
        )
    )
    object_id = factory.LazyAttribute(
        lambda obj: obj.content_item.pk if obj.content_item else None
    )


class LearnerCohortDeadlineOverrideFactory(SiteAwareFactory):
    """Factory for creating LearnerCohortDeadlineOverride instances.

    Pass ``content_item=<model instance>`` to set the GenericFK fields.
    When omitted, content_type and object_id default to None (course-level override).
    """

    class Meta:
        model = LearnerCohortDeadlineOverride
        exclude = ["content_item"]

    class Params:
        content_item = None

    cohort_course_registration = factory.SubFactory(CohortCourseRegistrationFactory)
    learner = factory.SubFactory(LearnerFactory)
    deadline = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    is_hard_deadline = False

    content_type = factory.LazyAttribute(
        lambda obj: (
            ContentType.objects.get_for_model(obj.content_item)
            if obj.content_item
            else None
        )
    )
    object_id = factory.LazyAttribute(
        lambda obj: obj.content_item.pk if obj.content_item else None
    )


class RecommendedCourseFactory(SiteAwareFactory):
    """Factory for creating RecommendedCourse instances."""

    class Meta:
        model = RecommendedCourse

    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)
