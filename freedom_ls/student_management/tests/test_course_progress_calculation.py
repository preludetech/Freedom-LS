import pytest
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    TopicFactory,
)
from freedom_ls.student_management.utils import calculate_course_progress_percentage


@pytest.mark.django_db
def test_course_with_no_children_returns_zero_percent(mock_site_context):
    """Course with no children should return 0% progress."""
    course = CourseFactory()
    percentage = calculate_course_progress_percentage(course, set(), set())
    assert percentage == 0


@pytest.mark.django_db
def test_course_with_one_topic_none_completed(mock_site_context):
    """Course with one topic and none completed should return 0%."""
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    percentage = calculate_course_progress_percentage(course, set(), set())
    assert percentage == 0


@pytest.mark.django_db
def test_course_with_one_topic_completed(mock_site_context):
    """Course with one topic completed should return 100%."""
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    completed_topics = {topic.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 100


@pytest.mark.django_db
def test_course_with_mixed_content(mock_site_context):
    """Course with mixed content types should calculate correctly."""
    course = CourseFactory()
    topic = TopicFactory()
    test_form = FormFactory()
    course.items.create(child=topic, order=0)
    course.items.create(child=test_form, order=1)

    # Only topic completed
    completed_topics = {topic.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 50


@pytest.mark.django_db
def test_course_with_multiple_items_partial_completion(mock_site_context):
    """Course with multiple items and partial completion."""
    course = CourseFactory()
    topic1 = TopicFactory(title="Topic 1")
    topic2 = TopicFactory(title="Topic 2")
    topic3 = TopicFactory(title="Topic 3")

    course.items.create(child=topic1, order=0)
    course.items.create(child=topic2, order=1)
    course.items.create(child=topic3, order=2)

    # 2 out of 3 completed
    completed_topics = {topic1.id, topic2.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 67  # round(66.666...)


@pytest.mark.django_db
def test_course_with_course_part_children(mock_site_context):
    """Course with CoursePart should count items inside the part."""
    course = CourseFactory()
    part = CoursePartFactory(title="Part 1")

    topic1 = TopicFactory(title="Topic 1")
    topic2 = TopicFactory(title="Topic 2")
    part.items.create(child=topic1, order=0)
    part.items.create(child=topic2, order=1)

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
def test_course_with_mixed_direct_and_part_children(mock_site_context):
    """Course with both direct items and items inside CourseParts."""
    course = CourseFactory()
    direct_topic = TopicFactory(title="Direct Topic")
    course.items.create(child=direct_topic, order=0)

    part = CoursePartFactory(title="Part 1")
    part_topic1 = TopicFactory(title="Part Topic 1")
    part_topic2 = TopicFactory(title="Part Topic 2")
    part.items.create(child=part_topic1, order=0)
    part.items.create(child=part_topic2, order=1)
    course.items.create(child=part, order=1)

    # Total: 3 items (1 direct + 2 in part)
    # Complete 2 out of 3
    completed_topics = {direct_topic.id, part_topic1.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 67  # round(66.666...)


@pytest.mark.django_db
def test_course_with_forms_in_course_part(mock_site_context):
    """Course with forms inside CourseParts."""
    course = CourseFactory()
    part = CoursePartFactory(title="Part 1")

    form1 = FormFactory(title="Form 1")
    form2 = FormFactory(title="Form 2")
    part.items.create(child=form1, order=0)
    part.items.create(child=form2, order=1)

    course.items.create(child=part, order=0)

    # One form completed
    completed_forms = {form1.id}
    percentage = calculate_course_progress_percentage(course, set(), completed_forms)
    assert percentage == 50
