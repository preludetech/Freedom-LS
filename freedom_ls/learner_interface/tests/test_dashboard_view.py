"""Tests for the learner dashboard view.

The dashboard view replaces the old ``partial_list_courses`` HTMX
endpoint; tests for that endpoint were deleted in the same change set.

Covers the dashboard's course sections (In progress, Learning history,
Recommended courses, Available courses) and the "Available courses" /
Browse-all-courses affordances.

Sections reach the template as one ordered ``sections`` list, so tests read
them through ``section_by_slug``.
"""

from __future__ import annotations

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory

from .conftest import (
    course_progress_record,
    rendered_section,
    section_by_slug,
)

# --- dashboard view ---


@pytest.mark.django_db
def test_dashboard_authenticated_returns_200_with_user_label(
    mock_site_context, courses, logged_in_client
):
    user = UserFactory(first_name="Ada")
    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    # The greeting renders the user's first name.
    assert "Ada" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_current_courses(mock_site_context, courses, logged_in_client):
    """Registered non-completed courses appear in the In progress section."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    in_progress = rendered_section(response, "in-progress")
    assert in_progress.courses == [courses[0]]
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_dedupes_a_course_registered_through_two_organisations(
    mock_site_context, courses, logged_in_client
):
    """A learner can hold two registrations for one course, one per
    organisation. The dashboard still lists that course exactly once."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user,
        course=courses[0],
        learner__organisation=OrganisationFactory(),
    )
    LearnerCourseRegistrationFactory(
        learner__user=user,
        course=courses[0],
        learner__organisation=OrganisationFactory(),
    )
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
    assert rendered_section(response, "in-progress").courses == [courses[0]]


@pytest.mark.django_db
def test_dashboard_current_courses_have_progress_percentage(
    mock_site_context, courses, logged_in_client
):
    """In-progress courses show progress_percentage attribute for progress bars."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    in_progress = rendered_section(response, "in-progress")
    assert len(in_progress.courses) == 1
    assert in_progress.courses[0].progress_percentage == 0


@pytest.mark.django_db
def test_dashboard_completed_courses(mock_site_context, courses, logged_in_client):
    """Completed courses surface in Learning history, not In progress."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(courses[0], user, completed_time=timezone.now())
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    assert courses[0] in rendered_section(response, "history").courses
    assert rendered_section(response, "in-progress").courses == []
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_removed_learner_lists_course_in_neither_section(
    mock_site_context, courses, logged_in_client
):
    """A removed learner's active registration grants nothing, so the course
    must not surface as either current or completed."""
    learner = LearnerFactory(is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, course=courses[0])
    client = logged_in_client(learner.user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
    assert courses[0] not in rendered_section(response, "in-progress").courses
    assert section_by_slug(response, "history") is None


@pytest.mark.django_db
def test_dashboard_recommended_courses(mock_site_context, courses, logged_in_client):
    """Recommended courses appear in the Recommended courses section."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    assert rendered_section(response, "recommended").courses == [courses[0]]
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_sorts_each_course_into_its_own_section(
    mock_site_context, courses, logged_in_client
):
    """Registered, completed and recommended courses land in three lists.

    The template reads `accent_slot_key` off whatever each list holds, so the
    courses have to arrive as Course objects rather than bare ids.
    """
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[1])
    course_progress_record(courses[1], user, completed_time=timezone.now())
    RecommendedCourseFactory(user=user, course=courses[2])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    in_progress = rendered_section(response, "in-progress")
    assert [course.pk for course in in_progress.courses] == [courses[0].pk]
    assert [course.pk for course in rendered_section(response, "history").courses] == [
        courses[1].pk
    ]
    assert [
        course.pk for course in rendered_section(response, "recommended").courses
    ] == [courses[2].pk]
    assert in_progress.courses[0].accent_slot_key == courses[0].accent_slot_key


# --- dashboard Available courses section ---


@pytest.mark.django_db
def test_dashboard_available_excludes_registered_and_completed(
    mock_site_context, courses, logged_in_client
):
    """Available list omits both in-progress and completed registrations."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[1])
    course_progress_record(courses[1], user, completed_time=timezone.now())
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    available = rendered_section(response, "available")
    assert courses[0] not in available.courses
    assert courses[1] not in available.courses


@pytest.mark.django_db
def test_dashboard_available_excludes_recommended(
    mock_site_context, courses, logged_in_client
):
    """Recommended courses do not also appear in the available list."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    assert courses[0] not in rendered_section(response, "available").courses


@pytest.mark.django_db
def test_dashboard_available_page_one_holds_three_of_five(
    mock_site_context, courses, logged_in_client
):
    """Page one shows the page size and says where in the section it sits."""
    user = UserFactory()
    CourseFactory(title="Course D", slug="course-d")
    CourseFactory(title="Course E", slug="course-e")
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    available = rendered_section(response, "available")
    assert len(available.courses) == 3
    assert available.position_text == "1 to 3 of 5"


@pytest.mark.django_db
def test_dashboard_available_includes_eligible_course(
    mock_site_context, courses, logged_in_client
):
    """A course with no registration or recommendation shows up as available."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    assert courses[0] in rendered_section(response, "available").courses


@pytest.mark.django_db
def test_dashboard_available_courses_are_not_registered(
    mock_site_context, courses, logged_in_client
):
    """An available course's card links to the course detail page, not into it."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    available = rendered_section(response, "available").courses
    assert [course.is_registered for course in available] == [False] * len(available)
    assert (
        reverse("learner_interface:course_detail", args=[available[0].slug])
        in response.content.decode()
    )


# --- dashboard "Available courses" section + Browse-all link ---


@pytest.mark.django_db
def test_dashboard_available_section_renders_browse_all_link(
    mock_site_context, courses, logged_in_client
):
    """When eligible courses exist, the section shows a Browse-all-courses link."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    body = response.content.decode()

    assert 'id="available-courses"' in body
    # A real anchor pointing at the all-courses page.
    courses_url = reverse("learner_interface:courses")
    assert f'href="{courses_url}"' in body


@pytest.mark.django_db
def test_dashboard_available_section_hidden_when_empty(
    mock_site_context, courses, logged_in_client
):
    """With no eligible courses, the whole section disappears."""
    user = UserFactory()
    # Register two and recommend the third -> nothing left to surface.
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[1])
    RecommendedCourseFactory(user=user, course=courses[2])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    assert section_by_slug(response, "available") is None
    body = response.content.decode()
    assert 'id="available-courses"' not in body


@pytest.mark.django_db
def test_dashboard_empty_state_prompts_a_learner_with_no_registrations(
    mock_site_context, courses, logged_in_client
):
    """A learner with no registrations sees the never-registered empty state."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    body = response.content.decode()
    assert 'data-testid="in-progress-empty-no-registrations"' in body


@pytest.mark.django_db
def test_dashboard_completed_course_in_history_not_available(
    mock_site_context, courses, logged_in_client
):
    """A completed course shows under Learning History, never under Available."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(courses[0], user, completed_time=timezone.now())
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    assert courses[0] in rendered_section(response, "history").courses
    assert courses[0] not in rendered_section(response, "available").courses
    body = response.content.decode()
    assert 'id="learning-history"' in body


@pytest.mark.django_db
def test_dashboard_empty_in_progress_reads_differently_once_there_is_history(
    mock_site_context, courses, logged_in_client
):
    """A learner who has finished everything has signed up for something.

    Completed courses move out to Learning History, so In Progress empties for
    a learner who is still registered — the never-signed-up copy would be
    plainly untrue for them.
    """
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(courses[0], user, completed_time=timezone.now())
    client = logged_in_client(user)

    body = client.get(reverse("learner_interface:dashboard")).content.decode()

    assert 'data-testid="in-progress-empty-no-registrations"' not in body
    assert 'data-testid="in-progress-empty-with-history"' in body
    assert 'id="learning-history"' in body
