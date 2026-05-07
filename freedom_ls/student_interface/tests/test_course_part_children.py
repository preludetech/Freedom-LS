import itertools

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart
from freedom_ls.student_interface.utils import (
    BLOCKED,
    IN_PROGRESS,
    READY,
    get_course_index,
)
from freedom_ls.student_management.factories import (
    UserCourseRegistrationFactory,
)
from freedom_ls.student_progress.factories import TopicProgressFactory


@pytest.mark.django_db
def test_course_part_children_have_status_and_url(mock_site_context):
    """Test that CoursePart children have proper status and url fields."""
    # Create a course with a CoursePart that contains children
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    course_part: CoursePart = CoursePartFactory(title="Chapter 1", slug="chapter-1")
    topic = TopicFactory(title="Topic 1", slug="topic-1", content="Test content")
    form = FormFactory(title="Quiz 1", slug="quiz-1")

    # Add course part as child of course
    course.items.create(child=course_part, order=0)

    # Add topic and form as children of course part
    course_part.items.create(child=topic, order=0)
    course_part.items.create(child=form, order=1)

    # Create a user and register them for the course
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)

    # Get the course index
    children = get_course_index(user=user, course=course)

    # Find the course part in the children
    course_part_dict = children[0]

    assert course_part_dict["type"] == "COURSE_PART"
    assert "children" in course_part_dict
    assert len(course_part_dict["children"]) == 2

    # Check that children have url and status
    topic_dict = course_part_dict["children"][0]
    assert topic_dict["title"] == "Topic 1"
    assert topic_dict["type"] == "TOPIC"
    assert "url" in topic_dict, "CoursePart child should have url"
    assert "status" in topic_dict, "CoursePart child should have status"
    assert topic_dict["status"] == READY  # First item should be READY
    assert topic_dict["url"] is not None  # Should have a URL

    form_dict = course_part_dict["children"][1]
    assert form_dict["title"] == "Quiz 1"
    assert form_dict["type"] == "FORM"
    assert "url" in form_dict
    assert "status" in form_dict
    assert form_dict["status"] == BLOCKED  # Second item should be BLOCKED


@pytest.mark.django_db
def test_course_part_status_based_on_children(mock_site_context):
    """Test that CoursePart status is calculated based on its children."""
    # Create a course with a CoursePart
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    course_part: CoursePart = CoursePartFactory(title="Chapter 1", slug="chapter-1")
    topic = TopicFactory(title="Topic 1", slug="topic-1", content="Test content")

    course.items.create(child=course_part, order=0)
    course_part.items.create(child=topic, order=0)

    # Create a user and register them
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)

    # Get the course index
    children = get_course_index(user=user, course=course)
    course_part_dict = children[0]

    # CoursePart should have READY status if first child is READY
    assert course_part_dict["status"] == READY
    # CoursePart URL should point to the READY child's URL
    topic_child_dict = course_part_dict["children"][0]
    assert course_part_dict["url"] == topic_child_dict["url"]


@pytest.mark.django_db
def test_course_part_row_url_resolves_to_first_viewable_child_index(mock_site_context):
    """A CoursePart's TOC row url must point to its first viewable child's URL."""
    course: Course = CourseFactory(title="Multi", slug="multi")
    p1: CoursePart = CoursePartFactory(title="P1", slug="p1")
    p2: CoursePart = CoursePartFactory(title="P2", slug="p2")
    p1a = TopicFactory(title="P1A", slug="p1a")
    p1b = TopicFactory(title="P1B", slug="p1b")
    p2a = TopicFactory(title="P2A", slug="p2a")

    course.items.create(child=p1, order=0)
    course.items.create(child=p2, order=1)
    p1.items.create(child=p1a, order=0)
    p1.items.create(child=p1b, order=1)
    p2.items.create(child=p2a, order=0)

    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    # Complete all viewable items so every item has a non-BLOCKED status (and thus a URL).
    now = timezone.now()
    for topic in (p1a, p1b, p2a):
        TopicProgressFactory(user=user, topic=topic, complete_time=now)

    children = get_course_index(user=user, course=course)

    # Independent oracle: viewable order is [p1a, p1b, p2a] -> indices [1, 2, 3].
    viewable_order = course.viewable_items()
    p1_first_child_idx = viewable_order.index(p1a) + 1
    p2_first_child_idx = viewable_order.index(p2a) + 1

    p1_dict = children[0]
    p2_dict = children[1]

    expected_p1_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": p1_first_child_idx},
    )
    expected_p2_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": p2_first_child_idx},
    )

    assert p1_dict["url"] == expected_p1_url
    assert p2_dict["url"] == expected_p2_url


@pytest.mark.django_db
def test_consecutive_viewable_items_have_dense_indices(mock_site_context):
    """URLs of consecutive viewable items in the TOC differ by exactly 1 in index."""
    course: Course = CourseFactory(title="Dense", slug="dense")
    p1: CoursePart = CoursePartFactory(title="P1", slug="p1")
    p2: CoursePart = CoursePartFactory(title="P2", slug="p2")
    p1a = TopicFactory(title="P1A", slug="p1a")
    p1b = TopicFactory(title="P1B", slug="p1b")
    p2a = TopicFactory(title="P2A", slug="p2a")
    direct = TopicFactory(title="Direct", slug="direct")

    course.items.create(child=p1, order=0)
    course.items.create(child=p2, order=1)
    course.items.create(child=direct, order=2)
    p1.items.create(child=p1a, order=0)
    p1.items.create(child=p1b, order=1)
    p2.items.create(child=p2a, order=0)

    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    # Complete all viewable items so every viewable row has a URL we can compare.
    now = timezone.now()
    for topic in (p1a, p1b, p2a, direct):
        TopicProgressFactory(user=user, topic=topic, complete_time=now)

    children = get_course_index(user=user, course=course)

    # Flatten viewable rows in URL-order: each part's children, then direct items.
    flat_rows = []
    for row in children:
        if "children" in row:
            flat_rows.extend(row["children"])
        else:
            flat_rows.append(row)

    indices = [int(row["url"].rstrip("/").rsplit("/", 1)[-1]) for row in flat_rows]
    diffs = [b - a for a, b in itertools.pairwise(indices)]
    assert diffs == [1] * len(diffs)
    # Sanity check: we actually had multiple rows to compare.
    assert len(indices) >= 2


@pytest.mark.django_db
def test_course_part_url_resumes_at_in_progress_child(mock_site_context):
    """When a part has a completed child and an in-progress child, the part row routes to in-progress."""
    course: Course = CourseFactory(title="Resume", slug="resume")
    part: CoursePart = CoursePartFactory(title="Chapter", slug="chapter")
    first = TopicFactory(title="First", slug="first", content="first")
    second = TopicFactory(title="Second", slug="second", content="second")
    third = TopicFactory(title="Third", slug="third", content="third")

    course.items.create(child=part, order=0)
    part.items.create(child=first, order=0)
    part.items.create(child=second, order=1)
    part.items.create(child=third, order=2)

    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    # First item completed; second item started but not complete.
    TopicProgressFactory(user=user, topic=first, complete_time=timezone.now())
    TopicProgressFactory(user=user, topic=second, complete_time=None)

    children = get_course_index(user=user, course=course)
    part_dict = children[0]

    second_index = course.viewable_items().index(second) + 1
    expected_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": second_index},
    )
    assert part_dict["status"] == IN_PROGRESS
    assert part_dict["url"] == expected_url


@pytest.mark.django_db
def test_course_part_url_skips_completed_first_child_to_first_ready(mock_site_context):
    """When the first child is complete and the next is READY, the part row routes to READY."""
    course: Course = CourseFactory(title="ReadyAfter", slug="ready-after")
    part: CoursePart = CoursePartFactory(title="Chapter", slug="chapter")
    first = TopicFactory(title="First", slug="first", content="first")
    second = TopicFactory(title="Second", slug="second", content="second")

    course.items.create(child=part, order=0)
    part.items.create(child=first, order=0)
    part.items.create(child=second, order=1)

    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    # Complete first item; second item has no progress (becomes READY).
    TopicProgressFactory(user=user, topic=first, complete_time=timezone.now())

    children = get_course_index(user=user, course=course)
    part_dict = children[0]

    second_index = course.viewable_items().index(second) + 1
    expected_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": second_index},
    )
    assert part_dict["status"] == READY
    assert part_dict["url"] == expected_url


@pytest.mark.django_db
def test_empty_course_part_row_has_no_url(mock_site_context):
    """A CoursePart with no viewable children gets url=None."""
    course: Course = CourseFactory(title="WithEmpty", slug="with-empty")
    empty_part: CoursePart = CoursePartFactory(title="Empty", slug="empty")
    course.items.create(child=empty_part, order=0)

    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)

    children = get_course_index(user=user, course=course)

    assert children[0]["url"] is None
