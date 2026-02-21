import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.test import RequestFactory
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Form,
    Topic,
)
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Student,
)

User = get_user_model()


@pytest.fixture
def educator_user(mock_site_context):
    """Create an educator user."""
    return User.objects.create_user(
        email="educator@example.com", password="testpass", is_staff=True
    )


@pytest.fixture
def cohort(mock_site_context):
    """Create a test cohort."""
    return Cohort.objects.create(name="Test Cohort")


@pytest.fixture
def course(mock_site_context):
    """Create a test course."""
    return Course.objects.create(title="Test Course", slug="test-course")


@pytest.fixture
def cohort_course_reg(mock_site_context, cohort, course):
    """Create a cohort course registration."""
    return CohortCourseRegistration.objects.create(
        cohort=cohort, collection=course, is_active=True
    )


@pytest.fixture
def request_factory(mock_site_context):
    """Create a request factory."""
    return RequestFactory()


def make_student(mock_site_context, email: str, cohort: Cohort) -> Student:
    """Create a student with a user and cohort membership."""
    user = User.objects.create_user(email=email, password="testpass")
    student = Student.objects.create(user=user)
    CohortMembership.objects.create(student=student, cohort=cohort)
    return student


def add_item_to_collection(collection, child, order=0):
    """Helper to add a child item to a course or course part."""
    collection_ct = DjangoContentType.objects.get_for_model(collection)
    child_ct = DjangoContentType.objects.get_for_model(child)
    return ContentCollectionItem.objects.create(
        collection_type=collection_ct,
        collection_id=collection.id,
        child_type=child_ct,
        child_id=child.id,
        order=order,
    )
