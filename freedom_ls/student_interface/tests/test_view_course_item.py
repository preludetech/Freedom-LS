"""Tests for view_course_item with nested course structure."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from freedom_ls.content_engine.models import Course, CoursePart, Topic, Form, FormPage
from freedom_ls.student_management.models import Student, StudentCourseRegistration

User = get_user_model()


@pytest.fixture
def course_with_nested_structure(mock_site_context, request):
    """
    Create a course with nested structure for testing flattened indices.

    Structure:
      - CoursePart "Chapter 1" (index 1)
        - First content item (index 2)
        - Second content item (index 3)
      - Third content item (index 4, direct child of course)

    Can be parameterized with first_item_type to use Topic or Form.
    Returns dict with course and all content items.
    """
    first_item_type = getattr(request, 'param', Topic)  # Default to Topic

    course = Course.objects.create(title="Test Course", slug="test-course")
    course_part = CoursePart.objects.create(title="Chapter 1", slug="chapter-1")

    if first_item_type == Topic:
        first_item = Topic.objects.create(
            title="First Topic",
            slug="first-topic",
            content="First item inside course part"
        )
    else:  # Form
        first_item = Form.objects.create(
            title="First Form",
            slug="first-form",
        )
        # Add a page to the form so it can be filled out
        FormPage.objects.create(
            form=first_item,
            title="Page 1",
            slug="page-1",
            order=0,
        )

    second_topic = Topic.objects.create(
        title="Second Topic",
        slug="second-topic",
        content="Second item inside course part"
    )

    third_topic = Topic.objects.create(
        title="Third Topic",
        slug="third-topic",
        content="Direct child of course"
    )

    # Build the structure
    course.items.create(child=course_part, order=0)
    course_part.items.create(child=first_item, order=0)
    course_part.items.create(child=second_topic, order=1)
    course.items.create(child=third_topic, order=1)

    return {
        "course": course,
        "course_part": course_part,
        "first_item": first_item,
        "second_item": second_topic,
        "third_item": third_topic,
    }


@pytest.fixture
def registered_user(mock_site_context, course_with_nested_structure):
    """Create a user registered for the test course."""
    user = User.objects.create_user(email="test@example.com", password="password")
    student = Student.objects.create(user=user)
    StudentCourseRegistration.objects.create(
        student=student,
        collection=course_with_nested_structure["course"]
    )
    return user


@pytest.fixture
def authenticated_client(registered_user):
    """Create an authenticated test client."""
    client = Client()
    client.force_login(registered_user)
    return client


@pytest.mark.django_db
def test_accessing_topic_inside_course_part_should_display_topic(
    course_with_nested_structure, authenticated_client
):
    """
    Test that clicking on a topic inside a course part actually displays that topic.

    Regression test for bug where view_course_item used course.children() (non-flattened)
    with indices from get_course_index() (flattened), causing wrong items to be displayed.
    """
    first_topic = course_with_nested_structure["first_item"]

    # The first topic inside the course part should be at index 2
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "test-course", "index": 2}
    )

    response = authenticated_client.get(url)

    # Should display the correct topic, not redirect
    assert response.status_code == 200, f"Should return 200, not redirect. Got {response.status_code}"
    assert "topic" in response.context, "Should have topic in context"
    actual_topic = response.context["topic"]
    assert actual_topic == first_topic, (
        f"Should display 'First Topic', but got '{actual_topic.title}'"
    )


@pytest.mark.django_db
@pytest.mark.parametrize('course_with_nested_structure', [Form], indirect=True)
def test_starting_form_inside_course_part_should_work(
    course_with_nested_structure, authenticated_client
):
    """
    Test that starting a form inside a course part works correctly.

    Ensures form_start view uses flattened indices like view_course_item.
    """
    first_form = course_with_nested_structure["first_item"]

    # The first form inside the course part should be at index 2
    url = reverse(
        "student_interface:form_start",
        kwargs={"course_slug": "test-course", "index": 2}
    )

    response = authenticated_client.get(url, follow=True)

    # Should successfully handle the form
    assert response.status_code == 200
    assert "form" in response.context, "Should have form in context"
    actual_form = response.context["form"]
    assert actual_form == first_form, (
        f"Should work with 'First Form', but got '{actual_form.title}'"
    )


@pytest.mark.django_db
@pytest.mark.parametrize('course_with_nested_structure', [Form], indirect=True)
def test_form_complete_inside_course_part_should_work(
    course_with_nested_structure, authenticated_client
):
    """
    Test that viewing form completion page for a form inside a course part works.

    Ensures course_form_complete view uses flattened indices.
    """
    first_form = course_with_nested_structure["first_item"]

    # The first form inside the course part should be at index 2
    url = reverse(
        "student_interface:course_form_complete",
        kwargs={"course_slug": "test-course", "index": 2}
    )

    response = authenticated_client.get(url)

    # Should successfully display the form complete page
    assert response.status_code == 200
    assert "form" in response.context, "Should have form in context"
    actual_form = response.context["form"]
    assert actual_form == first_form, (
        f"Should display completion for 'First Form', but got '{actual_form.title}'"
    )
