import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart
from freedom_ls.student_interface.utils import BLOCKED, READY, get_course_index
from freedom_ls.student_management.factories import (
    UserCourseRegistrationFactory,
)


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
