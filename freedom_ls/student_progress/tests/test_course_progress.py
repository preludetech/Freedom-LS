import pytest
from django.utils import timezone
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    TopicFactory,
)
from freedom_ls.student_progress.models import CourseProgress
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.conftest import add_item_to_collection


@pytest.mark.django_db
def test_course_progress_has_progress_percentage_field(mock_site_context):
    """Test that CourseProgress has a progress_percentage field that defaults to 0."""
    course_progress = CourseProgressFactory()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_course_progress_progress_percentage_can_be_set(mock_site_context):
    """Test that progress_percentage can be set to a specific value."""
    progress = CourseProgressFactory(progress_percentage=50)
    progress.refresh_from_db()
    assert progress.progress_percentage == 50


@pytest.mark.django_db
def test_completing_topic_updates_progress_percentage(mock_site_context):
    """Test that completing a topic updates progress_percentage on the related CourseProgress."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    add_item_to_collection(course, topic, order=0)
    course_progress = CourseProgressFactory(user=user, course=course)

    # Complete the topic
    tp = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_form_updates_progress_percentage(mock_site_context):
    """Test that completing a form updates progress_percentage on the related CourseProgress."""
    user = UserFactory()
    course = CourseFactory()
    form = FormFactory(strategy="QUIZ")
    add_item_to_collection(course, form, order=0)
    course_progress = CourseProgressFactory(user=user, course=course)

    # Complete the form via complete() method
    fp = FormProgressFactory(user=user, form=form)
    fp.complete()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_item_in_course_part_updates_parent_course(mock_site_context):
    """Test that completing an item inside a CoursePart traces up to the parent Course."""
    user = UserFactory()
    course = CourseFactory()
    part = CoursePartFactory()
    topic = TopicFactory()
    add_item_to_collection(course, part, order=0)
    add_item_to_collection(part, topic, order=0)
    course_progress = CourseProgressFactory(user=user, course=course)

    tp = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_item_in_multiple_courses_updates_all(mock_site_context):
    """Test that completing an item appearing in multiple courses updates all CourseProgress records."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course2 = CourseFactory()

    add_item_to_collection(course, topic, order=0)
    add_item_to_collection(course2, topic, order=0)

    cp1 = CourseProgressFactory(user=user, course=course)
    cp2 = CourseProgressFactory(user=user, course=course2)

    tp = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    cp1.refresh_from_db()
    cp2.refresh_from_db()
    assert cp1.progress_percentage == 100
    assert cp2.progress_percentage == 100


@pytest.mark.django_db
def test_progress_percentage_zero_when_no_items_complete(mock_site_context):
    """Test that progress_percentage is 0 when no items are complete."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    add_item_to_collection(course, topic, order=0)
    course_progress = CourseProgressFactory(user=user, course=course)

    # Start but don't complete
    TopicProgressFactory(user=user, topic=topic)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_completing_item_creates_course_progress_if_missing(mock_site_context):
    """Test that completing an item creates a CourseProgress record if one doesn't exist."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    add_item_to_collection(course, topic, order=0)

    # No CourseProgress exists yet
    assert CourseProgress.objects.filter(user=user, course=course).count() == 0

    tp = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    # CourseProgress should be created with correct percentage
    cp = CourseProgress.objects.get(user=user, course=course)
    assert cp.progress_percentage == 100


@pytest.mark.django_db
def test_partial_completion_gives_correct_percentage(mock_site_context):
    """Test that partial completion gives correct percentage (e.g. 2 of 4 items = 50%)."""
    user = UserFactory()
    course = CourseFactory()
    topics = [TopicFactory() for _ in range(4)]
    for i, topic in enumerate(topics):
        add_item_to_collection(course, topic, order=i)

    course_progress = CourseProgressFactory(user=user, course=course)

    # Complete 2 of 4 topics
    for topic in topics[:2]:
        tp = TopicProgressFactory(user=user, topic=topic)
        tp.complete_time = timezone.now()
        tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 50
