"""Tests for course_detail visibility behaviour (Task 4.1).

Covers the three detail-page rules added for coming-soon / hidden courses:
  * hidden + unregistered -> 404; hidden + registered -> 200 accessible.
  * coming_soon detail renders the shared express-interest affordance (not the
    generic enrol button), reflecting the user's current interest state.
  * published detail unchanged (still renders the generic CTA).
"""

from __future__ import annotations

import pytest

from django.test import override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.student_management.factories import UserCourseRegistrationFactory


def _detail_url(course: Course) -> str:
    return reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_hidden_course_unregistered_user_gets_404(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    client = logged_in_client(UserFactory())

    response = client.get(_detail_url(course))

    assert response.status_code == 404


@pytest.mark.django_db
def test_hidden_course_registered_user_gets_200(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
    client = logged_in_client(user)

    response = client.get(_detail_url(course))

    assert response.status_code == 200


@pytest.mark.django_db
def test_coming_soon_detail_renders_express_interest_not_enrol(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(_detail_url(course))
    body = response.content.decode()

    assert response.status_code == 200
    assert "I'm interested" in body
    assert "Enrol & start" not in body


@pytest.mark.django_db
def test_coming_soon_detail_default_state_is_not_interested(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(_detail_url(course))
    body = response.content.decode()

    assert "I'm interested" in body
    assert "Remove interest" not in body


@pytest.mark.django_db
def test_coming_soon_detail_interested_state_when_interest_exists(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    user = UserFactory()
    CourseInterestFactory(user=user, course=course)
    client = logged_in_client(user)

    response = client.get(_detail_url(course))
    body = response.content.decode()

    assert "Remove interest" in body
    assert "I'm interested" not in body


@pytest.mark.django_db
def test_coming_soon_registered_user_gets_generic_cta_not_express_interest(
    mock_site_context, course_with_topic, logged_in_client
):
    """A registered learner on a coming-soon course keeps the normal registered CTA.

    coming_soon exempts already-registered learners, so the detail page must not
    show the express-interest control (which would bounce / hide their content).
    """
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
    client = logged_in_client(user)

    response = client.get(_detail_url(course))
    body = response.content.decode()

    assert response.status_code == 200
    assert "I'm interested" not in body


@pytest.mark.django_db
def test_published_detail_renders_generic_cta(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(
        visibility=CourseVisibility.PUBLISHED, slug="published-course"
    )
    client = logged_in_client(UserFactory())

    response = client.get(_detail_url(course))
    body = response.content.decode()

    # The free backend's acquisition CTA for an unregistered learner on a
    # published course is "Enrol for free"; the express-interest affordance must
    # not appear for a published course.
    assert response.status_code == 200
    assert "Enrol for free" in body
    assert "I'm interested" not in body


# --- OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE ---


@pytest.mark.django_db
def test_hidden_course_unregistered_user_gets_200_with_visibility_override(
    mock_site_context, course_with_topic, logged_in_client
):
    course = course_with_topic(visibility=CourseVisibility.HIDDEN, slug="hidden-course")
    client = logged_in_client(UserFactory())

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        get_course_access_backend.cache_clear()
        response = client.get(_detail_url(course))

    assert response.status_code == 200


@pytest.mark.django_db
def test_coming_soon_detail_shows_generic_cta_with_visibility_override(
    mock_site_context, course_with_topic, logged_in_client
):
    """With the override on, a coming-soon course looks fully published: the
    generic enrol CTA renders instead of the express-interest affordance."""
    course = course_with_topic(
        visibility=CourseVisibility.COMING_SOON, slug="coming-soon-course"
    )
    client = logged_in_client(UserFactory())

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        get_course_access_backend.cache_clear()
        response = client.get(_detail_url(course))
    body = response.content.decode()

    assert response.status_code == 200
    assert "I'm interested" not in body
