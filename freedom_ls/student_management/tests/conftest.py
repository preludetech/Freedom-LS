import pytest
from django.contrib.contenttypes.models import ContentType
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.student_management.models import (
    Student,
    Cohort,
    CohortMembership,
    CohortCourseRegistration,
    StudentCourseRegistration,
)


@pytest.fixture
def course(mock_site_context):
    return Course.objects.create(title="Test Course", slug="test-course")


@pytest.fixture
def topic(mock_site_context):
    return Topic.objects.create(title="Test Topic", slug="test-topic")


@pytest.fixture
def student(mock_site_context, user):
    return Student.objects.create(user=user)


@pytest.fixture
def cohort(mock_site_context):
    return Cohort.objects.create(name="Test Cohort")


@pytest.fixture
def cohort_membership(mock_site_context, student, cohort):
    return CohortMembership.objects.create(student=student, cohort=cohort)


@pytest.fixture
def cohort_course_reg(mock_site_context, cohort, course):
    return CohortCourseRegistration.objects.create(
        cohort=cohort, collection=course
    )


@pytest.fixture
def student_course_reg(mock_site_context, student, course):
    return StudentCourseRegistration.objects.create(
        student=student, collection=course
    )


@pytest.fixture
def topic_ct():
    return ContentType.objects.get_for_model(Topic)
