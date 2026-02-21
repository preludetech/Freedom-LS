import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from freedom_ls.content_engine.models import (
    Course,
    CoursePart,
    Topic,
    Form,
    ContentCollectionItem,
)
from freedom_ls.student_progress.models import CourseProgress

User = get_user_model()


@pytest.fixture
def progress_user(mock_site_context):
    """Create a test user for progress tests."""
    return User.objects.create_user(email="progress@example.com", password="testpass")


@pytest.fixture
def progress_course(mock_site_context):
    """Create a test course for progress tests."""
    return Course.objects.create(title="Test Course", slug="test-course")


@pytest.fixture
def course_progress(mock_site_context, progress_user, progress_course):
    """Create a CourseProgress record."""
    return CourseProgress.objects.create(user=progress_user, course=progress_course)


@pytest.fixture
def topic_factory(mock_site_context):
    """Factory for creating topics."""
    counter = 0

    def _create(title=None, slug=None):
        nonlocal counter
        counter += 1
        title = title or f"Topic {counter}"
        slug = slug or f"topic-{counter}"
        return Topic.objects.create(title=title, slug=slug)

    return _create


@pytest.fixture
def form_factory(mock_site_context):
    """Factory for creating forms."""
    counter = 0

    def _create(title=None, strategy="QUIZ"):
        nonlocal counter
        counter += 1
        title = title or f"Form {counter}"
        return Form.objects.create(title=title, strategy=strategy)

    return _create


def add_item_to_collection(collection, child, order=0):
    """Helper to add a child item to a course or course part via ContentCollectionItem."""
    collection_ct = DjangoContentType.objects.get_for_model(collection)
    child_ct = DjangoContentType.objects.get_for_model(child)
    return ContentCollectionItem.objects.create(
        collection_type=collection_ct,
        collection_id=collection.id,
        child_type=child_ct,
        child_id=child.id,
        order=order,
    )


@pytest.fixture
def course_part_factory(mock_site_context):
    """Factory for creating course parts."""
    counter = 0

    def _create(title=None, slug=None):
        nonlocal counter
        counter += 1
        title = title or f"Course Part {counter}"
        slug = slug or f"course-part-{counter}"
        return CoursePart.objects.create(title=title, slug=slug)

    return _create
