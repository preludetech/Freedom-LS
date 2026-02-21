import pytest
from freedom_ls.student_progress.models import CourseProgress


@pytest.mark.django_db
def test_course_progress_has_progress_percentage_field(course_progress):
    """Test that CourseProgress has a progress_percentage field that defaults to 0."""
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_course_progress_progress_percentage_can_be_set(
    mock_site_context, progress_user, progress_course
):
    """Test that progress_percentage can be set to a specific value."""
    progress = CourseProgress.objects.create(
        user=progress_user, course=progress_course, progress_percentage=50
    )
    progress.refresh_from_db()
    assert progress.progress_percentage == 50
