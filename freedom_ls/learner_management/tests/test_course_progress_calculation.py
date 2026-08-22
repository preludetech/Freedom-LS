import pytest

from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart, Form, Topic
from freedom_ls.student_management.utils import calculate_course_progress_percentage


@pytest.mark.django_db
def test_course_with_no_children_returns_zero_percent(mock_site_context):
    """Course with no children should return 0% progress."""
    course: Course = CourseFactory()
    percentage = calculate_course_progress_percentage(course, set(), set())
    assert percentage == 0


@pytest.mark.parametrize(
    ("completed", "total", "expected"),
    [
        (0, 1, 0),
        (1, 1, 100),
        (1, 2, 50),
        (1, 3, 33),
        (2, 3, 67),
        (3, 4, 75),
        (1, 4, 25),
    ],
    ids=[
        "0_of_1_is_0",
        "1_of_1_is_100",
        "1_of_2_is_50",
        "1_of_3_is_33",
        "2_of_3_is_67",
        "3_of_4_is_75",
        "1_of_4_is_25",
    ],
)
@pytest.mark.django_db
def test_progress_percentage_for_n_of_m(mock_site_context, completed, total, expected):
    """Hard-coded oracles for completed/total → percentage. Oracles written down, not derived."""
    course: Course = CourseFactory()
    topics = [TopicFactory(title=f"Topic {i}") for i in range(total)]
    for i, topic in enumerate(topics):
        course.items.create(child=topic, order=i)
    completed_topic_ids = {t.id for t in topics[:completed]}

    percentage = calculate_course_progress_percentage(
        course, completed_topic_ids, set()
    )

    assert percentage == expected


@pytest.mark.django_db
def test_course_with_mixed_content(mock_site_context):
    """Course with mixed content types (Topic + Form) should calculate correctly."""
    course: Course = CourseFactory()
    topic: Topic = TopicFactory()
    test_form: Form = FormFactory()
    course.items.create(child=topic, order=0)
    course.items.create(child=test_form, order=1)

    # Only topic completed
    completed_topics = {topic.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 50


@pytest.mark.django_db
def test_course_with_course_part_children(mock_site_context):
    """Course with CoursePart should count items inside the part."""
    course: Course = CourseFactory()
    part: CoursePart = CoursePartFactory(title="Part 1")

    topic1: Topic = TopicFactory(title="Topic 1")
    topic2: Topic = TopicFactory(title="Topic 2")
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
    course: Course = CourseFactory()
    direct_topic: Topic = TopicFactory(title="Direct Topic")
    course.items.create(child=direct_topic, order=0)

    part: CoursePart = CoursePartFactory(title="Part 1")
    part_topic1: Topic = TopicFactory(title="Part Topic 1")
    part_topic2: Topic = TopicFactory(title="Part Topic 2")
    part.items.create(child=part_topic1, order=0)
    part.items.create(child=part_topic2, order=1)
    course.items.create(child=part, order=1)

    # Total: 3 items (1 direct + 2 in part)
    # Complete 2 out of 3
    completed_topics = {direct_topic.id, part_topic1.id}
    percentage = calculate_course_progress_percentage(course, completed_topics, set())
    assert percentage == 67  # (2 of 3) → 67


@pytest.mark.django_db
def test_course_with_forms_in_course_part(mock_site_context):
    """Course with forms inside CourseParts."""
    course: Course = CourseFactory()
    part: CoursePart = CoursePartFactory(title="Part 1")

    form1: Form = FormFactory(title="Form 1")
    form2: Form = FormFactory(title="Form 2")
    part.items.create(child=form1, order=0)
    part.items.create(child=form2, order=1)

    course.items.create(child=part, order=0)

    # One form completed
    completed_forms = {form1.id}
    percentage = calculate_course_progress_percentage(course, set(), completed_forms)
    assert percentage == 50
