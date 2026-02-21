import pytest
from django.contrib.auth import get_user_model
from freedom_ls.content_engine.models import Course
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
