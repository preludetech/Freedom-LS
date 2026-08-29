"""Deletion semantics for the registration and deadline models.

Registrations PROTECT their course; the deadline models SET_NULL their
content_type on a deleted ContentType and keep reading as a whole-course
deadline afterward.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.deadline_utils import (
    get_course_deadlines,
    get_effective_deadlines,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCohortDeadlineOverrideFactory,
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
)

pytestmark = pytest.mark.django_db


def _delete_content_type_for(instance: object) -> None:
    """Delete a model's ContentType row without poisoning the process-wide cache.

    ``ContentType.objects.get_for_model()`` caches the Python object it
    returns; calling ``.delete()`` on that cached instance mutates its ``pk``
    to ``None`` in place, so a later test's ``get_for_model()`` call for the
    same model would hand back an already-"deleted" instance. Deleting
    through a fresh queryset instead leaves that cached instance untouched.
    """
    content_type = ContentType.objects.get_for_model(instance)
    ContentType.objects.filter(pk=content_type.pk).delete()


class TestRegistrationCourseProtect:
    def test_deleting_a_course_with_a_learner_registration_is_blocked(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory()

        with pytest.raises(ProtectedError), transaction.atomic():
            registration.course.delete()

    def test_deleting_a_course_with_a_cohort_registration_is_blocked(
        self, mock_site_context
    ):
        registration = CohortCourseRegistrationFactory()

        with pytest.raises(ProtectedError), transaction.atomic():
            registration.course.delete()


class TestDeadlineContentTypeSetNull:
    def test_deleting_the_content_type_leaves_cohort_deadline_as_whole_course(
        self, mock_site_context
    ):
        topic = TopicFactory()
        deadline = CohortDeadlineFactory(content_item=topic)

        _delete_content_type_for(topic)

        deadline.refresh_from_db()
        assert deadline.content_type is None
        assert deadline.object_id == topic.pk
        deadline.full_clean()
        assert deadline.content_item is None

    def test_deleting_the_content_type_leaves_learner_deadline_as_whole_course(
        self, mock_site_context
    ):
        topic = TopicFactory()
        deadline = LearnerDeadlineFactory(content_item=topic)

        _delete_content_type_for(topic)

        deadline.refresh_from_db()
        assert deadline.content_type is None
        assert deadline.object_id == topic.pk
        deadline.full_clean()
        assert deadline.content_item is None

    def test_deleting_the_content_type_leaves_override_as_whole_course(
        self, mock_site_context
    ):
        topic = TopicFactory()
        membership = CohortMembershipFactory()
        registration = CohortCourseRegistrationFactory(cohort=membership.cohort)
        override = LearnerCohortDeadlineOverrideFactory(
            cohort_course_registration=registration,
            learner=membership.learner,
            content_item=topic,
        )

        _delete_content_type_for(topic)

        override.refresh_from_db()
        assert override.content_type is None
        assert override.object_id == topic.pk
        override.full_clean()
        assert override.content_item is None


class TestOrphanedDeadlineResolvesAsWholeCourse:
    """A deadline stripped of its content type is a whole-course deadline.

    ``object_id`` survives the ``SET_NULL``, so the row keeps pointing at a
    content item that no deadline lookup can reach any more. Resolution has to
    read it the same way ``clean()`` and ``__str__`` already do.
    """

    def test_cohort_deadline_resolves_for_the_whole_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        topic = TopicFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(learner__user=user, cohort=cohort)
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        deadline_dt = timezone.now() + timedelta(days=7)
        CohortDeadlineFactory(
            cohort_course_registration=registration,
            content_item=topic,
            deadline=deadline_dt,
        )

        _delete_content_type_for(topic)

        resolved = get_effective_deadlines(user, course)

        assert [effective.deadline for effective in resolved] == [deadline_dt]

    def test_learner_deadline_resolves_for_the_whole_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        topic = TopicFactory()
        registration = LearnerCourseRegistrationFactory(
            learner__user=user, course=course
        )
        deadline_dt = timezone.now() + timedelta(days=7)
        LearnerDeadlineFactory(
            learner_course_registration=registration,
            content_item=topic,
            deadline=deadline_dt,
        )

        _delete_content_type_for(topic)

        resolved = get_effective_deadlines(user, course)

        assert [effective.deadline for effective in resolved] == [deadline_dt]

    def test_override_resolves_for_the_whole_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        topic = TopicFactory()
        membership = CohortMembershipFactory(learner__user=user)
        registration = CohortCourseRegistrationFactory(
            cohort=membership.cohort, course=course
        )
        override_dt = timezone.now() + timedelta(days=14)
        LearnerCohortDeadlineOverrideFactory(
            cohort_course_registration=registration,
            learner=membership.learner,
            content_item=topic,
            deadline=override_dt,
        )

        _delete_content_type_for(topic)

        resolved = get_effective_deadlines(user, course)

        assert [effective.deadline for effective in resolved] == [override_dt]

    def test_bulk_resolution_keys_the_orphan_under_the_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        topic = TopicFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(learner__user=user, cohort=cohort)
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        deadline_dt = timezone.now() + timedelta(days=7)
        CohortDeadlineFactory(
            cohort_course_registration=registration,
            content_item=topic,
            deadline=deadline_dt,
        )

        _delete_content_type_for(topic)

        resolved = get_course_deadlines(user, course)

        assert list(resolved) == [(None, None)]
        assert [effective.deadline for effective in resolved[(None, None)]] == [
            deadline_dt
        ]
