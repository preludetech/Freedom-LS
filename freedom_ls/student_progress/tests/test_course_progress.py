import pytest
from django.utils import timezone
from freedom_ls.student_progress.models import (
    CourseProgress,
    TopicProgress,
    FormProgress,
)
from freedom_ls.student_progress.tests.conftest import add_item_to_collection


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


@pytest.mark.django_db
def test_completing_topic_updates_progress_percentage(
    mock_site_context, progress_user, progress_course, topic_factory
):
    """Test that completing a topic updates progress_percentage on the related CourseProgress."""
    topic = topic_factory()
    add_item_to_collection(progress_course, topic, order=0)
    course_progress = CourseProgress.objects.create(
        user=progress_user, course=progress_course
    )

    # Complete the topic
    tp = TopicProgress.objects.create(user=progress_user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_form_updates_progress_percentage(
    mock_site_context, progress_user, progress_course, form_factory
):
    """Test that completing a form updates progress_percentage on the related CourseProgress."""
    form = form_factory(strategy="QUIZ")
    add_item_to_collection(progress_course, form, order=0)
    course_progress = CourseProgress.objects.create(
        user=progress_user, course=progress_course
    )

    # Complete the form via complete() method
    fp = FormProgress.objects.create(user=progress_user, form=form)
    fp.complete()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_item_in_course_part_updates_parent_course(
    mock_site_context,
    progress_user,
    progress_course,
    topic_factory,
    course_part_factory,
):
    """Test that completing an item inside a CoursePart traces up to the parent Course."""
    part = course_part_factory()
    topic = topic_factory()
    add_item_to_collection(progress_course, part, order=0)
    add_item_to_collection(part, topic, order=0)
    course_progress = CourseProgress.objects.create(
        user=progress_user, course=progress_course
    )

    tp = TopicProgress.objects.create(user=progress_user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_item_in_multiple_courses_updates_all(
    mock_site_context, progress_user, progress_course, topic_factory
):
    """Test that completing an item appearing in multiple courses updates all CourseProgress records."""
    from freedom_ls.content_engine.models import Course

    topic = topic_factory()
    course2 = Course.objects.create(title="Second Course", slug="second-course")

    add_item_to_collection(progress_course, topic, order=0)
    add_item_to_collection(course2, topic, order=0)

    cp1 = CourseProgress.objects.create(user=progress_user, course=progress_course)
    cp2 = CourseProgress.objects.create(user=progress_user, course=course2)

    tp = TopicProgress.objects.create(user=progress_user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    cp1.refresh_from_db()
    cp2.refresh_from_db()
    assert cp1.progress_percentage == 100
    assert cp2.progress_percentage == 100


@pytest.mark.django_db
def test_progress_percentage_zero_when_no_items_complete(
    mock_site_context, progress_user, progress_course, topic_factory
):
    """Test that progress_percentage is 0 when no items are complete."""
    topic = topic_factory()
    add_item_to_collection(progress_course, topic, order=0)
    course_progress = CourseProgress.objects.create(
        user=progress_user, course=progress_course
    )

    # Start but don't complete
    TopicProgress.objects.create(user=progress_user, topic=topic)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_completing_item_creates_course_progress_if_missing(
    mock_site_context, progress_user, progress_course, topic_factory
):
    """Test that completing an item creates a CourseProgress record if one doesn't exist."""
    topic = topic_factory()
    add_item_to_collection(progress_course, topic, order=0)

    # No CourseProgress exists yet
    assert CourseProgress.objects.filter(
        user=progress_user, course=progress_course
    ).count() == 0

    tp = TopicProgress.objects.create(user=progress_user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    # CourseProgress should be created with correct percentage
    cp = CourseProgress.objects.get(user=progress_user, course=progress_course)
    assert cp.progress_percentage == 100


@pytest.mark.django_db
def test_partial_completion_gives_correct_percentage(
    mock_site_context, progress_user, progress_course, topic_factory
):
    """Test that partial completion gives correct percentage (e.g. 2 of 4 items = 50%)."""
    topics = [topic_factory() for _ in range(4)]
    for i, topic in enumerate(topics):
        add_item_to_collection(progress_course, topic, order=i)

    course_progress = CourseProgress.objects.create(
        user=progress_user, course=progress_course
    )

    # Complete 2 of 4 topics
    for topic in topics[:2]:
        tp = TopicProgress.objects.create(user=progress_user, topic=topic)
        tp.complete_time = timezone.now()
        tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 50
