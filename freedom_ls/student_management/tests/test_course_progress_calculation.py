import pytest
from freedom_ls.content_engine.models import Course, Topic, Form, CoursePart
from freedom_ls.student_management.utils import calculate_course_progress_percentage


@pytest.fixture
def course(mock_site_context):
    return Course.objects.create(
        title="Test Course",
        slug="test-course",
    )


@pytest.fixture
def topic(mock_site_context):
    return Topic.objects.create(
        title="Test Topic",
        slug="test-topic",
    )


@pytest.fixture
def test_form(mock_site_context):
    return Form.objects.create(
        title="Test Form",
        slug="test-form",
    )


@pytest.mark.django_db
def test_course_with_no_children_returns_zero_percent(course):
    """Course with no children should return 0% progress."""
    percentage = calculate_course_progress_percentage(course, set(), set())
    assert percentage == 0


@pytest.mark.django_db
def test_course_with_one_topic_none_completed(course, topic):
    """Course with one topic and none completed should return 0%."""
    course.items.create(child=topic, order=0)

    percentage = calculate_course_progress_percentage(course, set(), set())
    assert percentage == 0


@pytest.mark.django_db
def test_course_with_one_topic_completed(course, topic):
    """Course with one topic completed should return 100%."""
    course.items.create(child=topic, order=0)

    completed_topics = {topic.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 100


@pytest.mark.django_db
def test_course_with_mixed_content(course, topic, test_form):
    """Course with mixed content types should calculate correctly."""
    course.items.create(child=topic, order=0)
    course.items.create(child=test_form, order=1)

    # Only topic completed
    completed_topics = {topic.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 50


@pytest.mark.django_db
def test_course_with_multiple_items_partial_completion(course, mock_site_context):
    """Course with multiple items and partial completion."""
    topic1 = Topic.objects.create(title="Topic 1", slug="topic-1")
    topic2 = Topic.objects.create(title="Topic 2", slug="topic-2")
    topic3 = Topic.objects.create(title="Topic 3", slug="topic-3")

    course.items.create(child=topic1, order=0)
    course.items.create(child=topic2, order=1)
    course.items.create(child=topic3, order=2)

    # 2 out of 3 completed
    completed_topics = {topic1.id, topic2.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 67  # round(66.666...)


@pytest.mark.django_db
def test_course_with_course_part_children(course, mock_site_context):
    """Course with CoursePart should count items inside the part."""
    # Create a CoursePart
    part = CoursePart.objects.create(title="Part 1", slug="part-1")

    # Add topics to the part
    topic1 = Topic.objects.create(title="Topic 1", slug="topic-1")
    topic2 = Topic.objects.create(title="Topic 2", slug="topic-2")
    part.items.create(child=topic1, order=0)
    part.items.create(child=topic2, order=1)

    # Add the part to the course
    course.items.create(child=part, order=0)

    # No items completed
    percentage = calculate_course_progress_percentage(course, set(), set())
    assert percentage == 0

    # One item completed
    completed_topics = {topic1.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 50

    # Both items completed
    completed_topics = {topic1.id, topic2.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 100


@pytest.mark.django_db
def test_course_with_mixed_direct_and_part_children(course, mock_site_context):
    """Course with both direct items and items inside CourseParts."""
    # Direct topic
    direct_topic = Topic.objects.create(title="Direct Topic", slug="direct-topic")
    course.items.create(child=direct_topic, order=0)

    # CoursePart with topics
    part = CoursePart.objects.create(title="Part 1", slug="part-1")
    part_topic1 = Topic.objects.create(title="Part Topic 1", slug="part-topic-1")
    part_topic2 = Topic.objects.create(title="Part Topic 2", slug="part-topic-2")
    part.items.create(child=part_topic1, order=0)
    part.items.create(child=part_topic2, order=1)
    course.items.create(child=part, order=1)

    # Total: 3 items (1 direct + 2 in part)
    # Complete 2 out of 3
    completed_topics = {direct_topic.id, part_topic1.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 67  # round(66.666...)


@pytest.mark.django_db
def test_course_with_forms_in_course_part(course, mock_site_context):
    """Course with forms inside CourseParts."""
    part = CoursePart.objects.create(title="Part 1", slug="part-1")

    form1 = Form.objects.create(title="Form 1", slug="form-1")
    form2 = Form.objects.create(title="Form 2", slug="form-2")
    part.items.create(child=form1, order=0)
    part.items.create(child=form2, order=1)

    course.items.create(child=part, order=0)

    # One form completed
    completed_forms = {form1.id}
    percentage = calculate_course_progress_percentage(course, set(), completed_forms)
    assert percentage == 50
