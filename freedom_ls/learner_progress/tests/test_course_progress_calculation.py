import pytest

from freedom_ls.content_engine.factories import (
    ActivityFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart, Topic
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_progress.utils import calculate_course_progress_percentage


@pytest.mark.django_db
def test_course_with_no_children_returns_zero_percent(mock_site_context):
    """Course with no children should return 0% progress."""
    course: Course = CourseFactory()
    percentage = calculate_course_progress_percentage(course, set())
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
    placements = [
        course.items.create(child=TopicFactory(title=f"Topic {i}"), order=i)
        for i in range(total)
    ]
    completed_item_ids = {item.id for item in placements[:completed]}

    percentage = calculate_course_progress_percentage(course, completed_item_ids)

    assert percentage == expected


@pytest.mark.django_db
def test_course_with_mixed_content(mock_site_context):
    """Course with mixed content types (Topic + Form) should calculate correctly."""
    course: Course = CourseFactory()
    topic: Topic = TopicFactory()
    test_form: Form = FormFactory()
    topic_item = course.items.create(child=topic, order=0)
    course.items.create(child=test_form, order=1)

    # Only topic completed
    percentage = calculate_course_progress_percentage(course, {topic_item.id})
    assert percentage == 50


@pytest.mark.django_db
def test_course_with_course_part_children(mock_site_context):
    """An item nested in a CoursePart still counts towards the course total."""
    course: Course = CourseFactory()
    part: CoursePart = CoursePartFactory(title="Part 1")

    topic1: Topic = TopicFactory(title="Topic 1")
    topic2: Topic = TopicFactory(title="Topic 2")
    item1 = part.items.create(child=topic1, order=0)
    part.items.create(child=topic2, order=1)

    course.items.create(child=part, order=0)

    percentage = calculate_course_progress_percentage(course, {item1.id})

    assert percentage == 50


@pytest.mark.django_db
def test_course_with_mixed_direct_and_part_children(mock_site_context):
    """Course with both direct items and items inside CourseParts."""
    course: Course = CourseFactory()
    direct_topic: Topic = TopicFactory(title="Direct Topic")
    direct_item = course.items.create(child=direct_topic, order=0)

    part: CoursePart = CoursePartFactory(title="Part 1")
    part_topic1: Topic = TopicFactory(title="Part Topic 1")
    part_topic2: Topic = TopicFactory(title="Part Topic 2")
    part_item1 = part.items.create(child=part_topic1, order=0)
    part.items.create(child=part_topic2, order=1)
    course.items.create(child=part, order=1)

    percentage = calculate_course_progress_percentage(
        course, {direct_item.id, part_item1.id}
    )
    assert percentage == 67


@pytest.mark.django_db
def test_one_topic_placed_twice_counts_as_two_items(mock_site_context):
    """Each placement of a twice-placed topic is completed on its own.

    The course outline reads the placement, so a content-keyed percentage would
    credit both positions for one completion and disagree with what the learner
    can see.
    """
    course: Course = CourseFactory()
    topic: Topic = TopicFactory(title="Placed twice")
    other: Topic = TopicFactory(title="Placed once")
    first_placement = course.items.create(child=topic, order=0)
    course.items.create(child=other, order=1)
    course.items.create(child=topic, order=2)

    percentage = calculate_course_progress_percentage(course, {first_placement.id})

    assert percentage == 33


@pytest.mark.django_db
def test_a_placed_activity_is_excluded_from_the_count(mock_site_context):
    """Activities are placeable but have no completion, so they are not counted."""
    course: Course = CourseFactory()
    topic_item = course.items.create(child=TopicFactory(title="Topic"), order=0)
    course.items.create(child=ActivityFactory(title="Activity"), order=1)

    percentage = calculate_course_progress_percentage(course, {topic_item.id})

    assert percentage == 100
