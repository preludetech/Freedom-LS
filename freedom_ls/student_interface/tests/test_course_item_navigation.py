"""Tests for prev/next navigation in view_course_item under the viewable-only index scheme."""

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart
from freedom_ls.student_management.factories import (
    UserCourseRegistrationFactory,
)


@pytest.fixture
def course_starting_with_part(mock_site_context):
    """
    Course shape:
      - CoursePart "Chapter 1" (no URL slot)
        - Topic "First" (index 1)
        - Topic "Second" (index 2)
      - Topic "Third" (index 3, direct child of course)
    """
    course: Course = CourseFactory(title="Course", slug="course-a")
    part: CoursePart = CoursePartFactory(title="Chapter 1", slug="part-a")
    first = TopicFactory(title="First", slug="first", content="first")
    second = TopicFactory(title="Second", slug="second", content="second")
    third = TopicFactory(title="Third", slug="third", content="third")

    course.items.create(child=part, order=0)
    part.items.create(child=first, order=0)
    part.items.create(child=second, order=1)
    course.items.create(child=third, order=1)

    return {
        "course": course,
        "first": first,
        "second": second,
        "third": third,
    }


@pytest.fixture
def two_part_course(mock_site_context):
    """
    Course shape:
      - CoursePart "P1"
        - Topic "P1-A" (index 1)
        - Topic "P1-B" (index 2)
      - CoursePart "P2"
        - Topic "P2-A" (index 3)
        - Topic "P2-B" (index 4)
    """
    course: Course = CourseFactory(title="MultiPart", slug="multi-part")
    p1: CoursePart = CoursePartFactory(title="P1", slug="p1")
    p2: CoursePart = CoursePartFactory(title="P2", slug="p2")
    p1a = TopicFactory(title="P1-A", slug="p1-a", content="p1a")
    p1b = TopicFactory(title="P1-B", slug="p1-b", content="p1b")
    p2a = TopicFactory(title="P2-A", slug="p2-a", content="p2a")
    p2b = TopicFactory(title="P2-B", slug="p2-b", content="p2b")

    course.items.create(child=p1, order=0)
    course.items.create(child=p2, order=1)
    p1.items.create(child=p1a, order=0)
    p1.items.create(child=p1b, order=1)
    p2.items.create(child=p2a, order=0)
    p2.items.create(child=p2b, order=1)

    return {
        "course": course,
        "p1a": p1a,
        "p1b": p1b,
        "p2a": p2a,
        "p2b": p2b,
    }


@pytest.fixture
def authenticated_client_for(mock_site_context):
    """Factory fixture: authenticated client registered for the given course."""

    def _make(course: Course) -> Client:
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course)
        client = Client()
        client.force_login(user)
        return client

    return _make


@pytest.mark.django_db
def test_first_viewable_item_has_no_previous_url(
    course_starting_with_part, authenticated_client_for
):
    """At index=1 of a course that begins with a CoursePart, previous_url is None."""
    course = course_starting_with_part["course"]
    client = authenticated_client_for(course)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["previous_url"] is None


@pytest.mark.django_db
def test_first_item_of_non_first_part_links_back_to_last_item_of_previous_part(
    two_part_course, authenticated_client_for
):
    """At index=3 (first item of P2), previous_url resolves to index=2 (last item of P1)."""
    course = two_part_course["course"]
    p1b = two_part_course["p1b"]
    client = authenticated_client_for(course)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 3},
    )
    response = client.get(url)

    assert response.status_code == 200
    expected_prev = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    assert response.context["previous_url"] == expected_prev

    # Following the previous URL should render P1-B with no redirect chain.
    prev_response = client.get(response.context["previous_url"])
    assert prev_response.status_code == 200
    assert prev_response.context["topic"] == p1b


@pytest.mark.django_db
def test_middle_of_part_prev_and_next_are_adjacent_viewables(
    two_part_course, authenticated_client_for
):
    """At index=2, previous_url ends with index=1 and next_url ends with index=3."""
    course = two_part_course["course"]
    client = authenticated_client_for(course)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["previous_url"] == reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response.context["next_url"] == reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 3},
    )


@pytest.mark.django_db
def test_last_item_of_part_next_links_to_first_item_of_next_part(
    two_part_course, authenticated_client_for
):
    """At index=2 (last of P1), next_url is index=3 and renders P2-A directly (no redirect)."""
    course = two_part_course["course"]
    p2a = two_part_course["p2a"]
    client = authenticated_client_for(course)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)
    next_url = response.context["next_url"]

    expected_next = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 3},
    )
    assert next_url == expected_next

    # Direct GET on next_url renders P2-A with status 200 (no redirect plumbing).
    next_response = client.get(next_url)
    assert next_response.status_code == 200
    assert next_response.context["topic"] == p2a


@pytest.mark.django_db
def test_last_item_of_course_has_no_next_url(two_part_course, authenticated_client_for):
    """At index=4 (last viewable item), next_url is None."""
    course = two_part_course["course"]
    client = authenticated_client_for(course)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 4},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["next_url"] is None
