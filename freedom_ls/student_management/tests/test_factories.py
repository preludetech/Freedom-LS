"""Tests for student_management factories."""

import pytest
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    RecommendedCourseFactory,
    StudentCohortDeadlineOverrideFactory,
    StudentCourseRegistrationFactory,
    StudentDeadlineFactory,
    StudentFactory,
)
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


@pytest.mark.django_db
class TestStudentFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        student = StudentFactory()
        assert isinstance(student, Student)
        assert student.pk is not None
        assert student.user is not None
        assert student.site == mock_site_context

    def test_optional_fields_default_to_none(self, mock_site_context: Site) -> None:
        student = StudentFactory()
        assert student.id_number is None
        assert student.date_of_birth is None
        assert student.cellphone is None

    def test_optional_fields_can_be_overridden(self, mock_site_context: Site) -> None:
        from datetime import date

        student = StudentFactory(
            id_number="ABC123",
            date_of_birth=date(2000, 1, 1),
            cellphone="0821234567",
        )
        assert student.id_number == "ABC123"
        assert student.date_of_birth == date(2000, 1, 1)
        assert student.cellphone == "0821234567"


@pytest.mark.django_db
class TestCohortFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        cohort = CohortFactory()
        assert isinstance(cohort, Cohort)
        assert cohort.pk is not None
        assert cohort.name.startswith("Cohort ")
        assert cohort.site == mock_site_context

    def test_name_can_be_overridden(self, mock_site_context: Site) -> None:
        cohort = CohortFactory(name="Custom Cohort")
        assert cohort.name == "Custom Cohort"

    def test_sequential_names_are_unique(self, mock_site_context: Site) -> None:
        c1 = CohortFactory()
        c2 = CohortFactory()
        assert c1.name != c2.name


@pytest.mark.django_db
class TestCohortMembershipFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        membership = CohortMembershipFactory()
        assert isinstance(membership, CohortMembership)
        assert membership.pk is not None
        assert isinstance(membership.student, Student)
        assert isinstance(membership.cohort, Cohort)

    def test_subfactories_create_related_objects(self, mock_site_context: Site) -> None:
        membership = CohortMembershipFactory()
        assert membership.student.pk is not None
        assert membership.cohort.pk is not None


@pytest.mark.django_db
class TestStudentCourseRegistrationFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        reg = StudentCourseRegistrationFactory()
        assert isinstance(reg, StudentCourseRegistration)
        assert reg.pk is not None
        assert isinstance(reg.student, Student)
        assert isinstance(reg.collection, Course)
        assert reg.is_active is True

    def test_is_active_can_be_overridden(self, mock_site_context: Site) -> None:
        reg = StudentCourseRegistrationFactory(is_active=False)
        assert reg.is_active is False


@pytest.mark.django_db
class TestCohortCourseRegistrationFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        reg = CohortCourseRegistrationFactory()
        assert isinstance(reg, CohortCourseRegistration)
        assert reg.pk is not None
        assert isinstance(reg.cohort, Cohort)
        assert isinstance(reg.collection, Course)
        assert reg.is_active is True

    def test_is_active_can_be_overridden(self, mock_site_context: Site) -> None:
        reg = CohortCourseRegistrationFactory(is_active=False)
        assert reg.is_active is False


@pytest.mark.django_db
class TestCohortDeadlineFactory:
    def test_creates_valid_instance_without_content_item(
        self, mock_site_context: Site
    ) -> None:
        deadline = CohortDeadlineFactory()
        assert isinstance(deadline, CohortDeadline)
        assert deadline.pk is not None
        assert deadline.cohort_course_registration is not None
        assert deadline.deadline is not None
        assert deadline.is_hard_deadline is False
        assert deadline.content_type is None
        assert deadline.object_id is None

    def test_creates_valid_instance_with_content_item(
        self, mock_site_context: Site
    ) -> None:
        topic = TopicFactory(title="Deadline Topic", slug="deadline-topic")
        deadline = CohortDeadlineFactory(content_item=topic)
        assert deadline.content_type == ContentType.objects.get_for_model(Topic)
        assert deadline.object_id == topic.pk

    def test_deadline_is_in_the_future(self, mock_site_context: Site) -> None:
        deadline = CohortDeadlineFactory()
        assert deadline.deadline > timezone.now()


@pytest.mark.django_db
class TestStudentDeadlineFactory:
    def test_creates_valid_instance_without_content_item(
        self, mock_site_context: Site
    ) -> None:
        deadline = StudentDeadlineFactory()
        assert isinstance(deadline, StudentDeadline)
        assert deadline.pk is not None
        assert deadline.student_course_registration is not None
        assert deadline.deadline is not None
        assert deadline.is_hard_deadline is False
        assert deadline.content_type is None
        assert deadline.object_id is None

    def test_creates_valid_instance_with_content_item(
        self, mock_site_context: Site
    ) -> None:
        topic = TopicFactory(title="Deadline Topic", slug="deadline-topic-s")
        deadline = StudentDeadlineFactory(content_item=topic)
        assert deadline.content_type == ContentType.objects.get_for_model(Topic)
        assert deadline.object_id == topic.pk


@pytest.mark.django_db
class TestStudentCohortDeadlineOverrideFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        override = StudentCohortDeadlineOverrideFactory()
        assert isinstance(override, StudentCohortDeadlineOverride)
        assert override.pk is not None
        assert override.cohort_course_registration is not None
        assert override.student is not None
        assert override.deadline is not None
        assert override.is_hard_deadline is False
        assert override.content_type is None
        assert override.object_id is None

    def test_creates_valid_instance_with_content_item(
        self, mock_site_context: Site
    ) -> None:
        topic = TopicFactory(title="Override Topic", slug="override-topic")
        override = StudentCohortDeadlineOverrideFactory(content_item=topic)
        assert override.content_type == ContentType.objects.get_for_model(Topic)
        assert override.object_id == topic.pk


@pytest.mark.django_db
class TestRecommendedCourseFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        rec = RecommendedCourseFactory()
        assert isinstance(rec, RecommendedCourse)
        assert rec.pk is not None
        assert rec.user is not None
        assert isinstance(rec.collection, Course)
        assert rec.site == mock_site_context
