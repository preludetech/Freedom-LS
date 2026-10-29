"""Tests for the learner dashboard."""

from __future__ import annotations

import datetime
import re
from dataclasses import replace
from datetime import UTC

import pytest
import time_machine

from django.contrib.auth.models import AnonymousUser
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    CourseCategoryFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CourseAudience, CourseVisibility
from freedom_ls.course_access.backends import (
    CourseAccessDecision,
    FreeOnlyCourseAccessBackend,
)
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.deadlines.models import DeadlineKind
from freedom_ls.learner_interface.tests.helpers import (
    cohort_override,
    learner_override,
    learner_with_two_grants,
    rendered_section,
    section_by_slug,
    set_due_date,
    topic_completion,
)
from freedom_ls.learner_interface.utils import (
    get_completed_courses,
    get_current_courses,
)
from freedom_ls.learner_interface.views import _visible_recommendations
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory

# Tests for the learner dashboard view.
#
# The dashboard view replaces the old ``partial_list_courses`` HTMX
# endpoint; tests for that endpoint were deleted in the same change set.
#
# Covers the dashboard's course sections (In progress, Learning history,
# Recommended courses, Available courses) and the "Available courses" /
# Browse-all-courses affordances.
#
# Sections reach the template as one ordered ``sections`` list, so tests read
# them through ``section_by_slug``.


@pytest.mark.django_db
@pytest.mark.parametrize("headers", [{}, {"HTTP_HX_REQUEST": "true"}])
def test_dashboard_response_varies_on_htmx_headers(
    mock_site_context, courses, logged_in_client, headers
):
    """A fragment and the full page share a URL, so the cache must key on htmx headers.

    Without ``Vary``, Back restored the cached section fragment as the whole page.
    """
    client = logged_in_client(UserFactory())
    response = client.get(reverse("learner_interface:dashboard"), **headers)
    vary = {h.strip().lower() for h in response["Vary"].split(",")}
    assert {"hx-request", "hx-target"} <= vary


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
    """A deactivated learner's active registration grants nothing, so the course
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


@pytest.mark.django_db
def test_recommended_section_offers_browse_all_courses(
    mock_site_context, courses, logged_in_client
):
    """The Recommended courses section links to the whole catalogue, like every
    other discovery section."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "recommended").browse_all_url == reverse(
        "learner_interface:courses"
    )


@pytest.mark.django_db
def test_coming_soon_section_offers_browse_all_courses(
    mock_site_context, logged_in_client
):
    """The Coming soon section links to the whole catalogue, like every other
    discovery section."""
    CourseFactory(
        title="Not Yet Course",
        slug="not-yet-course",
        visibility=CourseVisibility.COMING_SOON,
    )
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "coming-soon").browse_all_url == reverse(
        "learner_interface:courses"
    )


@pytest.mark.django_db
def test_the_learners_own_sections_offer_no_browse_all_courses(
    mock_site_context, courses, logged_in_client
):
    """In progress and Learning history are the learner's own lists, not a
    discovery section, so neither offers a Browse-all-courses link."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    course_progress_record(courses[1], user, completed_time=timezone.now())
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "in-progress").browse_all_url == ""
    assert rendered_section(response, "history").browse_all_url == ""


@pytest.mark.django_db
def test_coming_soon_fragment_carries_the_browse_all_courses_button(
    mock_site_context, logged_in_client
):
    """The htmx fragment for Coming soon — the response an in-page swap
    actually renders — carries the button, not just the section object."""
    CourseFactory(
        title="Not Yet Course",
        slug="not-yet-course",
        visibility=CourseVisibility.COMING_SOON,
    )
    client = logged_in_client(UserFactory())

    response = client.get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-coming-soon",
    )

    assert "Browse all courses" in response.content.decode()


# How the dashboard's discovery pool splits into sections.
#
# Only ``Course.dashboard_category`` decides where a course lands: the other
# categories a course belongs to are deliberately never consulted here. A
# coming-soon course is the one exception to "one course, one section". It
# renders in Coming soon and, if its dashboard category is shown, in that
# category's section too.


def ordered_course_ids(response) -> dict[str, list]:
    """Each rendered section's course ids, keyed by section slug."""
    return {
        section.slug: [course.pk for course in section.courses]
        for section in response.context["sections"]
    }


@pytest.mark.django_db
def test_course_lands_in_its_dashboard_category_section(mock_site_context):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    course = CourseFactory(
        title="Course A", slug="course-a", dashboard_category=category
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "start-here").courses == [course]
    assert section_by_slug(response, "available") is None


@pytest.mark.django_db
def test_uncategorised_course_lands_in_available_courses(mock_site_context):
    course = CourseFactory(title="Course A", slug="course-a")

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "available").courses == [course]


@pytest.mark.django_db
def test_hidden_category_course_lands_in_available_and_renders_no_section(
    mock_site_context,
):
    """A category flagged off the dashboard contributes no section, and its
    courses fall through to the catch-all rather than to another of their
    categories."""
    hidden = CourseCategoryFactory(
        title="Reference", slug="reference", show_on_dashboard=False
    )
    visible = CourseCategoryFactory(title="Assessment", slug="assessment")
    course = CourseFactory(title="Course A", slug="course-a", dashboard_category=hidden)
    course.categories.set([hidden, visible])

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "available").courses == [course]
    assert section_by_slug(response, "reference") is None
    assert section_by_slug(response, "assessment") is None


@pytest.mark.django_db
def test_course_in_three_categories_renders_only_in_its_dashboard_category(
    mock_site_context,
):
    start_here = CourseCategoryFactory(title="Start here", slug="start-here")
    assessment = CourseCategoryFactory(title="Assessment", slug="assessment")
    reference = CourseCategoryFactory(title="Reference", slug="reference")
    course = CourseFactory(
        title="Course A", slug="course-a", dashboard_category=assessment
    )
    course.categories.set([start_here, assessment, reference])

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "assessment").courses == [course]
    assert section_by_slug(response, "start-here") is None
    assert section_by_slug(response, "reference") is None


@pytest.mark.django_db
def test_coming_soon_course_renders_in_its_shown_category_and_in_coming_soon(
    mock_site_context,
):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    course = CourseFactory(
        title="Course A",
        slug="course-a",
        dashboard_category=category,
        visibility=CourseVisibility.COMING_SOON,
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "start-here").courses == [course]
    assert rendered_section(response, "coming-soon").courses == [course]


@pytest.mark.django_db
def test_coming_soon_courses_interleave_alphabetically_in_their_category(
    mock_site_context,
):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    alpha = CourseFactory(title="Alpha", slug="alpha", dashboard_category=category)
    bravo = CourseFactory(
        title="Bravo",
        slug="bravo",
        dashboard_category=category,
        visibility=CourseVisibility.COMING_SOON,
    )
    charlie = CourseFactory(
        title="Charlie", slug="charlie", dashboard_category=category
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    # Three courses, one page at SECTION_PAGE_SIZE: the order below is the
    # section's actual render order, not a second page boundary.
    assert rendered_section(response, "start-here").courses == [alpha, bravo, charlie]


@pytest.mark.django_db
def test_uncategorised_coming_soon_course_stays_out_of_available_courses(
    mock_site_context,
):
    course = CourseFactory(
        title="Course A", slug="course-a", visibility=CourseVisibility.COMING_SOON
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "coming-soon").courses == [course]
    assert section_by_slug(response, "available") is None


@pytest.mark.django_db
def test_hidden_category_coming_soon_course_stays_out_of_available_courses(
    mock_site_context,
):
    hidden = CourseCategoryFactory(
        title="Reference", slug="reference", show_on_dashboard=False
    )
    course = CourseFactory(
        title="Course A",
        slug="course-a",
        dashboard_category=hidden,
        visibility=CourseVisibility.COMING_SOON,
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "coming-soon").courses == [course]
    assert section_by_slug(response, "available") is None
    assert section_by_slug(response, "reference") is None


@pytest.mark.django_db
def test_a_category_of_only_coming_soon_courses_renders_a_section(mock_site_context):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    course = CourseFactory(
        title="Course A",
        slug="course-a",
        dashboard_category=category,
        visibility=CourseVisibility.COMING_SOON,
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "start-here").courses == [course]


@pytest.mark.django_db
def test_a_coming_soon_only_category_can_lead_the_page(
    mock_site_context, logged_in_client
):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    CourseFactory(
        title="Course A",
        slug="course-a",
        dashboard_category=category,
        visibility=CourseVisibility.COMING_SOON,
    )
    user = UserFactory()
    RecommendedCourseFactory(
        user=user, course=CourseFactory(title="Course B", slug="course-b")
    )

    response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

    slugs = [section.slug for section in response.context["sections"]]
    assert slugs.index("start-here") < slugs.index("recommended")


@pytest.mark.django_db
def test_visibility_override_puts_a_coming_soon_course_back_in_its_category(
    mock_site_context,
):
    """The split reads the override, not ``visibility`` alone, so the
    visibility preview keeps working."""
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    course = CourseFactory(
        title="Course A",
        slug="course-a",
        dashboard_category=category,
        visibility=CourseVisibility.COMING_SOON,
    )

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "start-here").courses == [course]
    assert section_by_slug(response, "coming-soon") is None


@pytest.mark.django_db
def test_category_sections_render_in_configured_order(mock_site_context):
    second = CourseCategoryFactory(title="Assessment", slug="assessment", order=2)
    first = CourseCategoryFactory(title="Start here", slug="start-here", order=1)
    CourseFactory(title="Course A", slug="course-a", dashboard_category=first)
    CourseFactory(title="Course B", slug="course-b", dashboard_category=second)

    response = Client().get(reverse("learner_interface:dashboard"))

    slugs = [section.slug for section in response.context["sections"]]
    assert slugs.index("start-here") < slugs.index("assessment")


@pytest.mark.django_db
def test_fifty_categories_render_fifty_sections(mock_site_context):
    for index in range(50):
        category = CourseCategoryFactory(
            title=f"Category {index}", slug=f"category-{index}", order=index
        )
        CourseFactory(
            title=f"Course {index}",
            slug=f"course-{index}",
            dashboard_category=category,
        )

    response = Client().get(reverse("learner_interface:dashboard"))

    category_slugs = [
        section.slug
        for section in response.context["sections"]
        if section.wrapper_id.startswith("category-")
    ]
    assert len(category_slugs) == 50


@pytest.mark.django_db
def test_category_with_no_visible_course_renders_nothing(mock_site_context):
    CourseCategoryFactory(title="Start here", slug="start-here")

    response = Client().get(reverse("learner_interface:dashboard"))

    assert section_by_slug(response, "start-here") is None
    assert 'id="category-start-here"' not in response.content.decode()


@pytest.mark.django_db
def test_headline_category_sits_above_recommended_courses(
    mock_site_context, logged_in_client
):
    """The first rendered category section is the site's headline group and
    outranks Recommended courses; the rest follow it."""
    first = CourseCategoryFactory(title="Start here", slug="start-here", order=1)
    second = CourseCategoryFactory(title="Assessment", slug="assessment", order=2)
    CourseFactory(title="Course A", slug="course-a", dashboard_category=first)
    CourseFactory(title="Course B", slug="course-b", dashboard_category=second)
    user = UserFactory()
    RecommendedCourseFactory(
        user=user, course=CourseFactory(title="Course C", slug="course-c")
    )

    response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

    slugs = [section.slug for section in response.context["sections"]]
    assert slugs.index("start-here") < slugs.index("recommended")
    assert slugs.index("recommended") < slugs.index("assessment")


@pytest.mark.django_db
def test_unconfigured_site_renders_todays_sections_in_todays_order(
    mock_site_context, courses, logged_in_client
):
    """With no categories declared, the dashboard is the page it was: In
    progress, Recommended courses, Available courses, Learning history."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[1])
    course_progress_record(courses[1], user, completed_time=timezone.now())
    RecommendedCourseFactory(user=user, course=courses[2])
    CourseFactory(title="Course D", slug="course-d")
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()

    assert [section.slug for section in response.context["sections"]] == [
        "in-progress",
        "recommended",
        "available",
        "history",
    ]
    assert f'href="{reverse("learner_interface:courses")}"' in body
    assert "Browse all courses" in body


@pytest.mark.django_db
def test_in_progress_drops_below_coming_soon_when_it_is_empty(
    mock_site_context, courses, logged_in_client
):
    CourseFactory(title="Soon", slug="soon", visibility=CourseVisibility.COMING_SOON)
    response = logged_in_client(UserFactory()).get(
        reverse("learner_interface:dashboard")
    )

    slugs = [section.slug for section in response.context["sections"]]
    assert slugs.index("coming-soon") < slugs.index("in-progress")


@pytest.mark.django_db
def test_one_coming_soon_course_renders_a_coming_soon_section(mock_site_context):
    course = CourseFactory(
        title="Course A", slug="course-a", visibility=CourseVisibility.COMING_SOON
    )

    response = Client().get(reverse("learner_interface:dashboard"))

    assert rendered_section(response, "coming-soon").courses == [course]
    assert 'id="coming-soon-courses"' in response.content.decode()


@pytest.mark.django_db
def test_repeated_renders_produce_the_same_order_in_every_section(
    mock_site_context, logged_in_client
):
    """Every tie-breaker exists so two renders of unchanged data agree."""
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    for index in range(5):
        CourseFactory(
            title=f"Course {index}",
            slug=f"course-{index}",
            dashboard_category=category,
        )
    client = logged_in_client(UserFactory())
    url = reverse("learner_interface:dashboard")

    first = client.get(url)
    second = client.get(url)

    assert ordered_course_ids(first) == ordered_course_ids(second)


# Tests for the deterministic ordering of in-progress, completed and
# recommended courses on the learner dashboard.


def _at(day: int) -> datetime.datetime:
    return datetime.datetime(2026, 1, day, tzinfo=datetime.UTC)


@pytest.mark.django_db
def test_started_course_ranks_before_unstarted_course_regardless_of_registration_order(
    mock_site_context,
):
    """A started course outranks an unstarted one even when registered later."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")

    # course_b is registered first, course_a second -- registration order
    # runs the opposite way to the expected result.
    LearnerCourseRegistrationFactory(learner__user=user, course=course_b)
    course_progress_record(course_a, user, started_at=_at(2))

    result = get_current_courses(user)

    assert result == [course_a, course_b]


@pytest.mark.django_db
def test_started_courses_order_by_most_recent_access(mock_site_context):
    """Within the started bucket, the most recently accessed course leads."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")

    # course_b started later than course_a but was accessed earlier, so a
    # sort on started_at would rank it first -- ranking must follow
    # last_accessed_time instead.
    course_progress_record(
        course_a, user, started_at=_at(1), last_accessed_time=_at(10)
    )
    course_progress_record(course_b, user, started_at=_at(5), last_accessed_time=_at(2))

    result = get_current_courses(user)

    assert result == [course_a, course_b]


@pytest.mark.django_db
def test_unstarted_courses_order_by_newest_registration(mock_site_context):
    """Within the unstarted bucket, the most recently registered course leads."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")

    # Both courses have a record (so registered_at is set) but neither has
    # been started.
    course_progress_record(course_a, user, created_at=_at(1))
    course_progress_record(course_b, user, created_at=_at(5))

    result = get_current_courses(user)

    assert result == [course_b, course_a]


@pytest.mark.django_db
def test_learning_history_orders_by_completion_date_descending(mock_site_context):
    """Completed courses list most recently completed first."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")

    course_progress_record(course_a, user, completed_time=_at(1))
    course_progress_record(course_b, user, completed_time=_at(10))

    result = get_completed_courses(user)

    assert result == [course_b, course_a]


@pytest.mark.django_db
def test_recommended_courses_order_newest_first(mock_site_context):
    """Recommendations list the most recently recommended course first."""
    user = UserFactory()
    course_a: Course = CourseFactory(title="Course A", slug="course-a")
    course_b: Course = CourseFactory(title="Course B", slug="course-b")
    older = RecommendedCourseFactory(user=user, course=course_a)
    newer = RecommendedCourseFactory(user=user, course=course_b)
    older.created_at = _at(1)
    older.save(update_fields=["created_at"])
    newer.created_at = _at(10)
    newer.save(update_fields=["created_at"])

    result = _visible_recommendations(user, get_course_access_backend())

    assert [rec.course for rec in result] == [course_b, course_a]


@pytest.mark.django_db
def test_recommended_courses_tie_broken_by_course_slug(mock_site_context):
    """Recommendations created at the same instant fall back to course slug."""
    user = UserFactory()
    course_z: Course = CourseFactory(title="Course Z", slug="course-z")
    course_a: Course = CourseFactory(title="Course A", slug="course-a")
    same_moment = _at(1)
    rec_z = RecommendedCourseFactory(user=user, course=course_z)
    rec_a = RecommendedCourseFactory(user=user, course=course_a)
    rec_z.created_at = same_moment
    rec_z.save(update_fields=["created_at"])
    rec_a.created_at = same_moment
    rec_a.save(update_fields=["created_at"])

    result = _visible_recommendations(user, get_course_access_backend())

    assert [rec.course for rec in result] == [course_a, course_z]


# Per-section paging on the dashboard: page state, clamping and the htmx branch.
#
# Page state is one namespaced query parameter per section, ``page_<slug>``,
# written only when that section is off page one.

DASHBOARD_URL = "/"


@pytest.fixture
def four_available_courses(mock_site_context) -> list:
    return [
        CourseFactory(title=f"Course {letter}", slug=f"course-{letter.lower()}")
        for letter in ["A", "B", "C", "D"]
    ]


@pytest.mark.django_db
def test_page_one_renders_three_and_reports_the_position(four_available_courses):
    response = Client().get(reverse("learner_interface:dashboard"))

    available = rendered_section(response, "available")
    assert available.courses == four_available_courses[:3]
    assert available.position_text == "1 to 3 of 4"


def _fragment(client: Client, slug: str, **params: str) -> str:
    response = client.get(
        reverse("learner_interface:dashboard"),
        params,
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET=f"section-page-{slug}",
    )
    return response.content.decode()


@pytest.mark.django_db
def test_each_section_renders_the_card_grid_and_the_row_list_with_the_same_courses(
    four_available_courses,
):
    body = _fragment(Client(), "available")

    assert body.count('data-testid="section-card-grid"') == 1
    assert body.count('data-testid="section-row-list"') == 1
    for course in four_available_courses[:3]:
        assert len(re.findall(rf">\s*{course.title}\s*</a>", body)) == 2


@pytest.mark.django_db
def test_browse_all_courses_renders_once_per_layout(
    mock_site_context, logged_in_client
):
    CourseFactory(
        title="Not Yet Course",
        slug="not-yet-course",
        visibility=CourseVisibility.COMING_SOON,
    )
    user = UserFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user, course=CourseFactory(title="Mine", slug="mine")
    )
    client = logged_in_client(user)

    assert _fragment(client, "coming-soon").count("Browse all courses") == 2
    assert _fragment(client, "in-progress").count("Browse all courses") == 0


@pytest.mark.django_db
def test_an_in_progress_row_resumes_at_the_next_item(
    mock_site_context, logged_in_client
):
    user = UserFactory()
    course = CourseFactory(title="Course A", slug="course-a")
    first = TopicFactory(title="Opening topic", slug="opening", content="content")
    second = TopicFactory(title="Second topic", slug="second", content="content")
    course.items.create(child=first, order=0)
    course.items.create(child=second, order=1)
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    topic_completion(course, user, first, complete_time=timezone.now())
    client = logged_in_client(user)

    body = _fragment(client, "in-progress")

    row_list = body.split('data-testid="section-row-list"')[1]
    item_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    assert f'href="{item_url}"' in row_list
    assert "Next up: Second topic" in row_list


@pytest.mark.django_db
def test_page_two_renders_the_fourth_course(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"), {"page_available": "2"}
    )

    available = rendered_section(response, "available")
    assert available.courses == [four_available_courses[3]]
    assert available.position_text == "4 to 4 of 4"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("page_value", "expected_page_courses"),
    [
        ("abc", slice(0, 3)),
        ("0", slice(0, 3)),
        ("-1", slice(0, 3)),
        ("9999", slice(3, 4)),
    ],
)
def test_a_bad_page_number_clamps_and_returns_200(
    four_available_courses, page_value, expected_page_courses
):
    response = Client().get(
        reverse("learner_interface:dashboard"), {"page_available": page_value}
    )

    assert response.status_code == 200
    assert (
        rendered_section(response, "available").courses
        == four_available_courses[expected_page_courses]
    )


@pytest.mark.django_db
def test_an_unrecognised_page_parameter_is_ignored(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"), {"page_no_such_section": "3"}
    )

    assert response.status_code == 200
    assert rendered_section(response, "available").courses == four_available_courses[:3]


@pytest.mark.django_db
def test_recommended_courses_page_like_the_rest(mock_site_context, logged_in_client):
    """Recommended is the one section whose rows are RecommendedCourse objects
    rather than courses, so a shared helper is most likely to miss it."""
    user = UserFactory()
    recommended = [
        CourseFactory(title=f"Course {letter}", slug=f"course-{letter.lower()}")
        for letter in ["A", "B", "C", "D"]
    ]
    for course in recommended:
        RecommendedCourseFactory(user=user, course=course)
    client = logged_in_client(user)

    first_page = client.get(reverse("learner_interface:dashboard"))
    second_page = client.get(
        reverse("learner_interface:dashboard"), {"page_recommended": "2"}
    )

    assert len(rendered_section(first_page, "recommended").courses) == 3
    assert rendered_section(first_page, "recommended").position_text == "1 to 3 of 4"
    assert len(rendered_section(second_page, "recommended").courses) == 1


@pytest.mark.django_db
def test_in_progress_pages(mock_site_context, logged_in_client):
    user = UserFactory()
    learner = LearnerFactory(user=user)
    for letter in ["A", "B", "C", "D"]:
        course = CourseFactory(
            title=f"Course {letter}", slug=f"course-{letter.lower()}"
        )
        LearnerCourseRegistrationFactory(learner=learner, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    in_progress = rendered_section(response, "in-progress")
    assert len(in_progress.courses) == 3
    assert in_progress.position_text == "1 to 3 of 4"


@pytest.mark.django_db
def test_an_htmx_request_returns_one_section_rather_than_the_page(
    four_available_courses,
):
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-available",
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert "<h1" not in body
    assert 'id="section-page-available"' in body
    assert four_available_courses[0].title in body


@pytest.mark.django_db
def test_the_same_url_without_the_htmx_header_returns_the_whole_page(
    four_available_courses,
):
    response = Client().get(reverse("learner_interface:dashboard"))

    assert "<h1" in response.content.decode()


@pytest.mark.django_db
def test_an_htmx_request_for_a_category_returns_that_category(mock_site_context):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    course: Course = CourseFactory(
        title="Course A", slug="course-a", dashboard_category=category
    )

    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-start-here",
    )

    assert response.status_code == 200
    assert course.title in response.content.decode()


@pytest.mark.django_db
def test_an_htmx_request_for_a_category_includes_its_coming_soon_course(
    mock_site_context,
):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    course: Course = CourseFactory(
        title="Course A",
        slug="course-a",
        dashboard_category=category,
        visibility=CourseVisibility.COMING_SOON,
    )

    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-start-here",
    )

    assert response.status_code == 200
    assert course.title in response.content.decode()


@pytest.mark.django_db
def test_an_htmx_request_with_no_target_header_returns_the_whole_page(
    four_available_courses,
):
    response = Client().get(
        reverse("learner_interface:dashboard"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    assert "<h1" in response.content.decode()


@pytest.mark.django_db
def test_a_boosted_request_returns_the_whole_page(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_BOOSTED="true",
        HTTP_HX_TARGET="interface-main",
    )

    assert response.status_code == 200
    assert "<h1" in response.content.decode()


@pytest.mark.django_db
def test_an_htmx_request_for_an_unknown_section_is_a_404(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-no-such-thing",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_anonymous_htmx_request_for_in_progress_is_a_404(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-in-progress",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_htmx_request_for_an_emptied_section_removes_that_section(
    mock_site_context,
):
    """A stale page click on a drained section takes the section off the page."""
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-available",
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert response["HX-Retarget"] == "#available-courses"
    assert response["HX-Reswap"] == "delete"
    assert 'id="section-page-available"' not in body
    assert 'id="dashboard-section-status"' in body
    assert "Available courses: nothing to show" in body


@pytest.mark.django_db
def test_an_htmx_request_for_an_emptied_in_progress_swaps_in_its_empty_state(
    mock_site_context,
):
    learner = LearnerFactory()
    client = Client()
    client.force_login(learner.user)

    response = client.get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-in-progress",
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert response["HX-Retarget"] == "#current-courses"
    assert response["HX-Reswap"] == "outerHTML"
    assert 'id="current-courses"' in body
    assert "in-progress-empty-no-registrations" in body
    assert "In progress: nothing to show" in body


@pytest.mark.django_db
def test_an_emptied_in_progress_with_history_points_at_the_history(
    mock_site_context,
):
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory(learner=learner)
    course_progress_record(
        registration.course, learner.user, completed_time=timezone.now()
    )
    client = Client()
    client.force_login(learner.user)

    response = client.get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-in-progress",
    )

    assert response.status_code == 200
    assert "in-progress-empty-with-history" in response.content.decode()


# Accessibility contract for the dashboard's paginated sections.
#
# Focus movement itself is JavaScript and is exercised in the browser, not here.
# What these pin is the markup that focus movement depends on: a control that
# never disappears, a heading outside the swap, and one live region.


def _dashboard_body(**headers: str) -> str:
    response = Client().get(reverse("learner_interface:dashboard"), **headers)
    return response.content.decode()


@pytest.mark.django_db
def test_both_controls_render_with_previous_disabled_on_page_one(
    four_available_courses,
):
    body = _dashboard_body()

    assert body.count('data-direction="previous"') == 1
    assert body.count('data-direction="next"') == 1
    assert re.search(
        r'aria-disabled="true"[^>]*data-direction="previous"', body, re.S
    ) or re.search(r'data-direction="previous"[^>]*aria-disabled="true"', body, re.S)


@pytest.mark.django_db
def test_the_next_control_is_disabled_on_the_last_page(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"), {"page_available": "2"}
    )
    body = response.content.decode()

    assert body.count('data-direction="next"') == 1
    assert re.search(
        r'data-direction="next"[^>]*aria-disabled="true"', body, re.S
    ) or re.search(r'aria-disabled="true"[^>]*data-direction="next"', body, re.S)


@pytest.mark.django_db
def test_a_disabled_control_never_uses_the_disabled_attribute(four_available_courses):
    """`disabled` would take the control out of the tab order, so focus could
    not return to the control the learner just pressed."""
    body = _dashboard_body()

    assert "disabled>" not in body
    assert 'aria-disabled="true"' in body


@pytest.mark.django_db
def test_each_section_nav_carries_a_unique_label(mock_site_context):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    CourseFactory(title="Course A", slug="course-a", dashboard_category=category)
    CourseFactory(title="Course B", slug="course-b")

    body = _dashboard_body()

    labels = re.findall(r'<nav aria-label="([^"]+) pages"', body)
    assert sorted(labels) == ["Available courses", "Start here"]


@pytest.mark.django_db
def test_the_heading_sits_outside_the_swapped_element(four_available_courses):
    body = _dashboard_body()

    heading_position = body.index('id="section-heading-available"')
    swap_position = body.index('id="section-page-available"')
    assert heading_position < swap_position


@pytest.mark.django_db
def test_the_heading_can_take_focus(four_available_courses):
    body = _dashboard_body()

    assert re.search(r'id="section-heading-available"\s+tabindex="-1"', body)


@pytest.mark.django_db
def test_the_page_carries_exactly_one_status_region(mock_site_context):
    CourseCategoryFactory(title="Start here", slug="start-here")
    CourseFactory(
        title="Course A",
        slug="course-a",
        dashboard_category=CourseCategoryFactory(title="Assessment", slug="assessment"),
    )
    CourseFactory(title="Course B", slug="course-b")

    body = _dashboard_body()

    assert body.count('id="dashboard-section-status"') == 1
    # The toast container carries the page's other role="status", so the
    # dashboard's own region is identified by aria-atomic.
    assert body.count('aria-atomic="true"') == 1


@pytest.mark.django_db
def test_the_whole_page_status_region_starts_empty_and_out_of_band_free(
    four_available_courses,
):
    body = _dashboard_body()

    assert 'id="dashboard-section-status"' in body
    assert "hx-swap-oob" not in body


@pytest.mark.django_db
def test_the_htmx_fragment_updates_the_status_region_out_of_band(
    four_available_courses,
):
    body = _dashboard_body(
        HTTP_HX_REQUEST="true", HTTP_HX_TARGET="section-page-available"
    )

    assert 'id="dashboard-section-status"' in body
    assert 'hx-swap-oob="true"' in body
    assert "Available courses: showing 1 to 3 of 4" in body


# Query-cost regression tests for the dashboard.
#
# The In progress and category-section builders run one access-decision lookup
# and one player-index build per course (`_annotate_registered_courses`,
# `_annotate_discovery_courses`), so a per-course query pinned to unbounded
# registration or category growth would defeat the pagination that caps each
# section's page size. Each test below pins a section's query count against a
# realistic-sized page and then grows the input that section must not be
# sensitive to, to prove the count held.

IN_PROGRESS_MAX_QUERIES = 60


CATEGORY_SECTION_MAX_QUERIES = 7


@pytest.mark.django_db
def test_in_progress_query_count_does_not_grow_with_registrations(
    mock_site_context, django_assert_max_num_queries, logged_in_client
):
    dashboard_url = reverse("learner_interface:dashboard")
    user = UserFactory()
    for _ in range(10):
        LearnerCourseRegistrationFactory(learner__user=user, course=CourseFactory())
    client = logged_in_client(user)

    with django_assert_max_num_queries(IN_PROGRESS_MAX_QUERIES):
        client.get(dashboard_url)

    LearnerCourseRegistrationFactory(learner__user=user, course=CourseFactory())

    with django_assert_max_num_queries(IN_PROGRESS_MAX_QUERIES):
        client.get(dashboard_url)


@pytest.mark.django_db
def test_category_section_query_count_does_not_grow_with_courses(
    mock_site_context, django_assert_max_num_queries
):
    dashboard_url = reverse("learner_interface:dashboard")
    category = CourseCategoryFactory(show_on_dashboard=True)
    for _ in range(10):
        CourseFactory(dashboard_category=category)
    client = Client()

    with django_assert_max_num_queries(CATEGORY_SECTION_MAX_QUERIES):
        client.get(dashboard_url)

    CourseFactory(dashboard_category=category)

    with django_assert_max_num_queries(CATEGORY_SECTION_MAX_QUERIES):
        client.get(dashboard_url)


@pytest.mark.django_db
def test_category_section_query_count_does_not_grow_with_categories_per_course(
    mock_site_context, django_assert_max_num_queries
):
    dashboard_url = reverse("learner_interface:dashboard")
    category = CourseCategoryFactory(show_on_dashboard=True)
    courses = [CourseFactory(dashboard_category=category) for _ in range(10)]
    # Off the dashboard, so they add no section of their own. This isolates
    # the cost of the many-to-many from the cost of an extra category section.
    other_categories = [
        CourseCategoryFactory(show_on_dashboard=False) for _ in range(4)
    ]
    courses[0].categories.set([category, *other_categories])
    client = Client()

    with django_assert_max_num_queries(CATEGORY_SECTION_MAX_QUERIES):
        client.get(dashboard_url)


# --- Deadline line on the In progress cards ---


@pytest.fixture
def deadline_card(mock_site_context, logged_in_client):
    """A course with two topics, a learner registered on 1 Mar 2026 and their client."""
    course = CourseFactory()
    topics = [TopicFactory(title="First Topic"), TopicFactory(title="Second Topic")]
    for order, topic in enumerate(topics):
        course.items.create(child=topic, order=order)
    user = UserFactory()
    record = course_progress_record(
        course, user, created_at=datetime.datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    )
    return course, topics, user, record, logged_in_client(user)


def _dashboard_html(client: Client | None = None) -> str:
    response = (client or Client()).get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
    return response.content.decode()


def _dashboard_text(client: Client) -> str:
    """The dashboard's visible text, tags stripped and whitespace collapsed."""
    return " ".join(re.sub(r"<[^>]+>", " ", _dashboard_html(client)).split())


def _first_card_grid(html: str) -> str:
    """The first section's card grid, without the row list that repeats each course."""
    start = html.index('data-testid="section-card-grid"')
    return html[start : html.index('data-testid="section-row-list"', start)]


def _row_lists(html: str) -> str:
    """Every section's row list, without the card grids that repeat each course."""
    return "".join(
        part.split('data-testid="section-card-grid"')[0]
        for part in html.split('data-testid="section-row-list"')[1:]
    )


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 9, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_shows_the_earliest_missed_deadline_across_topics_and_time_limit(
    deadline_card,
):
    course, topics, _user, _record, client = deadline_card
    course.time_limit_days = 30
    course.save()
    set_due_date(course, topics[1], due_date=datetime.date(2020, 1, 1))

    text = _dashboard_text(client)

    assert "Missed deadline Second Topic 1 Jan 2020" in text
    assert "Missed deadline Course " not in text
    assert "Next deadline" not in text


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 9, 1, 10, 0, tzinfo=UTC), tick=False)
def test_the_compact_row_shows_the_missed_deadline_too(deadline_card):
    """Below lg the section shows rows, which must carry the card's deadline line."""
    course, topics, _user, _record, client = deadline_card
    set_due_date(course, topics[1], due_date=datetime.date(2020, 1, 1))

    html = _dashboard_html(client)
    row_list = html[html.index('data-testid="section-row-list"') :]

    assert "Missed deadline" in row_list
    assert "Second Topic" in row_list


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 9, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_names_a_missed_time_limit_course(deadline_card):
    course, _topics, _user, _record, client = deadline_card
    course.time_limit_days = 30
    course.save()

    text = _dashboard_text(client)

    assert "Missed deadline Course 31 Mar 2026" in text
    assert "time limit" not in text.lower()
    assert "Overdue" not in text


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_shows_a_missed_deadline_ahead_of_the_next_deadline(deadline_card):
    course, topics, _user, _record, client = deadline_card
    set_due_date(course, topics[0], due_date=datetime.date(2999, 1, 1))
    set_due_date(course, topics[1], due_date=datetime.date(2020, 1, 1))

    text = _dashboard_text(client)

    assert "Missed deadline Second Topic 1 Jan 2020" in text
    assert "Next deadline" not in text
    assert "overdue" not in text.lower()


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_shows_the_earliest_of_several_missed_deadlines(deadline_card):
    course, topics, _user, _record, client = deadline_card
    set_due_date(course, topics[0], due_date=datetime.date(2021, 1, 1))
    set_due_date(course, topics[1], due_date=datetime.date(2020, 1, 1))

    text = _dashboard_text(client)

    assert "Missed deadline Second Topic 1 Jan 2020" in text
    assert "1 Jan 2021" not in text


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_shows_the_earliest_next_deadline_across_topics_and_time_limit(
    deadline_card,
):
    course, topics, _user, _record, client = deadline_card
    course.time_limit_days = 90
    course.save()
    set_due_date(course, topics[0], due_date=datetime.date(2999, 1, 1))
    set_due_date(course, topics[1], due_date=datetime.date(2998, 1, 1))

    text = _dashboard_text(client)

    assert "Next deadline: Course 30 May 2026" in text
    assert "Missed deadline" not in text


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_names_the_topic_of_the_next_deadline(deadline_card):
    course, topics, _user, _record, client = deadline_card
    set_due_date(course, topics[0], due_date=datetime.date(2999, 1, 1))

    text = _dashboard_text(client)

    assert "Next deadline: First Topic 1 Jan 2999" in text
    assert "Next due" not in text
    assert "overdue" not in text.lower()


@pytest.mark.django_db
def test_card_shows_no_deadline_line_without_deadlines(deadline_card):
    _course, _topics, _user, _record, client = deadline_card

    text = _dashboard_text(client)

    assert "Next deadline" not in text
    assert "Missed deadline" not in text


@pytest.mark.django_db
def test_card_ignores_a_completed_topics_missed_deadline(deadline_card):
    course, topics, user, _record, client = deadline_card
    set_due_date(course, topics[0], due_date=datetime.date(2020, 1, 1))
    topic_completion(course, user, topics[0], complete_time=timezone.now())

    text = _dashboard_text(client)

    assert "Missed deadline" not in text
    assert "1 Jan 2020" not in text


class ContentWithheldBackend(FreeOnlyCourseAccessBackend):
    """The free backend with content access withdrawn from everyone, as a downstream
    subscription backend would do for a lapsed learner."""

    def get_access(
        self, *, user: User | AnonymousUser, course: Course
    ) -> CourseAccessDecision:
        return replace(
            super().get_access(user=user, course=course), can_access_content=False
        )


@pytest.mark.django_db
def test_card_shows_no_deadline_line_when_content_access_is_withheld(deadline_card):
    """Without content access the index carries no progress, so a finished topic would
    otherwise read as missed."""
    course, topics, user, _record, client = deadline_card
    course.time_limit_days = 30
    course.save()
    set_due_date(course, topics[0], due_date=datetime.date(2020, 1, 1))
    topic_completion(course, user, topics[0], complete_time=timezone.now())

    with override_settings(COURSE_ACCESS_BACKEND=f"{__name__}.ContentWithheldBackend"):
        get_course_access_backend.cache_clear()
        text = _dashboard_text(client)

    assert "Missed deadline" not in text
    assert "Next deadline" not in text


@pytest.mark.django_db
def test_card_ignores_a_completed_topics_deadline_for_the_next_deadline(
    deadline_card,
):
    course, topics, user, _record, client = deadline_card
    set_due_date(course, topics[0], due_date=datetime.date(2999, 1, 1))
    set_due_date(course, topics[1], due_date=datetime.date(2999, 6, 1))
    topic_completion(course, user, topics[0], complete_time=timezone.now())

    text = _dashboard_text(client)

    assert "Next deadline: Second Topic 1 Jun 2999" in text
    assert "1 Jan 2999" not in text


@pytest.mark.django_db
def test_card_shows_a_learner_registered_today_a_fixed_past_date_missed(
    deadline_card,
):
    course, topics, _user, record, client = deadline_card
    record.created_at = timezone.now()
    record.save()
    set_due_date(course, topics[0], due_date=datetime.date(2020, 1, 1))

    assert "Missed deadline First Topic" in _dashboard_text(client)


@pytest.mark.django_db
def test_card_deadline_line_sits_below_next_up_and_outside_the_eyebrow(
    deadline_card,
):
    course, topics, _user, _record, client = deadline_card
    set_due_date(course, topics[0], due_date=datetime.date(2999, 1, 1))

    html = _first_card_grid(_dashboard_html(client))

    assert html.index("Next up:") < html.index("Next deadline")
    assert html.count("Next deadline") == 1


@pytest.mark.django_db
@pytest.mark.parametrize("show_label", [True, False])
def test_card_dates_follow_the_site_zone_label_setting(deadline_card, show_label):
    SiteTimeZoneConfigFactory(show_time_zone_to_learners=show_label)
    course, topics, _user, _record, client = deadline_card
    set_due_date(course, topics[0], due_date=datetime.date(2999, 1, 1))

    html = _dashboard_html(client)

    assert f'data-show-zone="{str(show_label).lower()}"' in html


@pytest.mark.django_db
def test_in_progress_query_count_does_not_grow_with_cards_carrying_deadlines(
    mock_site_context, django_assert_max_num_queries, logged_in_client
):
    dashboard_url = reverse("learner_interface:dashboard")
    user = UserFactory()
    for _ in range(10):
        course = CourseFactory(time_limit_days=30)
        topic = TopicFactory()
        course.items.create(child=topic, order=0)
        set_due_date(course, topic, due_date=datetime.date(2020, 1, 1))
        course_progress_record(course, user)
    client = logged_in_client(user)

    with django_assert_max_num_queries(IN_PROGRESS_MAX_QUERIES):
        response = client.get(dashboard_url)

    card_count = len(rendered_section(response, "in-progress").courses)
    assert card_count > 1
    assert (
        _first_card_grid(response.content.decode()).count("Missed deadline")
        == card_count
    )


@pytest.mark.django_db
def test_card_still_names_the_next_up_topic(deadline_card):
    _course, topics, _user, _record, client = deadline_card

    assert f"Next up: {topics[0].title}" in _dashboard_text(client)


# --- Cohort deadline overrides on the dashboard card ---


@pytest.fixture
def overridden_card(deadline_card, logged_in_client):
    """The deadline card course with its first topic due in 2020, plus a cohort learner."""
    course, topics, _user, _record, individual_client = deadline_card
    item = set_due_date(course, topics[0], due_date=datetime.date(2020, 1, 1))
    cohort_user, cohort_record, _ = learner_with_two_grants(course)
    return item, cohort_record, logged_in_client(cohort_user), individual_client


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_cohort_override_beats_the_content_default(overridden_card):
    item, record, client, _ = overridden_card
    cohort_override(
        record,
        item,
        kind=DeadlineKind.FIXED,
        due_date=datetime.date(2999, 1, 1),
        due_days_after_registration=None,
    )

    text = _dashboard_text(client)

    assert "Next deadline: First Topic 1 Jan 2999" in text
    assert "Missed deadline" not in text


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_none_override_removes_the_date(overridden_card):
    item, record, client, _ = overridden_card
    cohort_override(
        record, item, kind=DeadlineKind.NONE, due_days_after_registration=None
    )

    text = _dashboard_text(client)

    assert "Missed deadline" not in text
    assert "Next deadline" not in text


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_individual_registration_ignores_the_cohort_override(overridden_card):
    item, record, _, individual_client = overridden_card
    cohort_override(
        record, item, kind=DeadlineKind.NONE, due_days_after_registration=None
    )

    assert "Missed deadline First Topic" in _dashboard_text(individual_client)


# --- Learner deadline overrides on the dashboard card ---


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_learner_override_beats_the_cohort_override_and_the_default(
    overridden_card,
):
    item, record, client, _ = overridden_card
    cohort_override(
        record,
        item,
        kind=DeadlineKind.FIXED,
        due_date=datetime.date(2030, 1, 1),
        due_days_after_registration=None,
    )
    learner_override(
        record,
        item,
        kind=DeadlineKind.FIXED,
        due_date=datetime.date(2999, 1, 1),
        due_days_after_registration=None,
    )

    text = _dashboard_text(client)

    assert "Next deadline: First Topic 1 Jan 2999" in text
    assert "1 Jan 2030" not in text
    assert "Missed deadline" not in text


@pytest.mark.django_db
@time_machine.travel(datetime.datetime(2026, 4, 1, 10, 0, tzinfo=UTC), tick=False)
def test_card_learner_none_override_removes_the_date(overridden_card):
    item, record, client, _ = overridden_card
    learner_override(
        record, item, kind=DeadlineKind.NONE, due_days_after_registration=None
    )

    text = _dashboard_text(client)

    assert "Missed deadline" not in text
    assert "Next deadline" not in text


# Organisation byline on dashboard cards.


@pytest.mark.django_db
def test_discovery_card_names_the_single_organisation(mock_site_context):
    course = CourseFactory(audience=CourseAudience.PUBLIC)
    course.organisations.add(OrganisationFactory(name="Solo Academy"))

    assert "Solo Academy" in _dashboard_html()


@pytest.mark.django_db
def test_discovery_card_names_no_organisation_for_a_course_with_none(
    mock_site_context,
):
    CourseFactory()
    OrganisationFactory(name="Unrelated Academy")

    assert "Unrelated Academy" not in _dashboard_html()


@pytest.mark.django_db
def test_discovery_card_names_no_organisation_for_a_course_with_several(
    mock_site_context,
):
    course = CourseFactory(audience=CourseAudience.PUBLIC)
    course.organisations.add(
        OrganisationFactory(name="First Academy"),
        OrganisationFactory(name="Second Academy"),
    )

    html = _dashboard_html()

    assert "First Academy" not in html
    assert "Second Academy" not in html


@pytest.mark.django_db
def test_coming_soon_card_names_the_single_organisation(mock_site_context):
    course = CourseFactory(
        visibility=CourseVisibility.COMING_SOON, audience=CourseAudience.PUBLIC
    )
    course.organisations.add(OrganisationFactory(name="Soon Academy"))

    assert "Soon Academy" in _dashboard_html()


@pytest.mark.django_db
def test_recommended_card_names_the_single_organisation(
    mock_site_context, logged_in_client
):
    user = UserFactory()
    course = CourseFactory(audience=CourseAudience.PUBLIC)
    course.organisations.add(OrganisationFactory(name="Rec Academy"))
    RecommendedCourseFactory(user=user, course=course)

    assert "Rec Academy" in _dashboard_html(logged_in_client(user))


@pytest.mark.django_db
def test_in_progress_card_names_the_organisation_the_learner_studies_through(
    mock_site_context, logged_in_client
):
    user = UserFactory()
    course = CourseFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user,
        learner__organisation=OrganisationFactory(name="Study Academy"),
        course=course,
    )
    course_progress_record(course, user)

    assert "Study Academy" in _dashboard_html(logged_in_client(user))


@pytest.mark.django_db
def test_in_progress_card_names_the_organisation_of_a_cohort_registration(
    mock_site_context, logged_in_client
):
    user = UserFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=OrganisationFactory(name="Cohort Academy"))
    CohortMembershipFactory(cohort=cohort, learner__user=user)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    course_progress_record(course, user)

    assert "Cohort Academy" in _dashboard_html(logged_in_client(user))


@pytest.mark.django_db
def test_discovery_row_names_the_single_organisation(mock_site_context):
    course = CourseFactory(audience=CourseAudience.PUBLIC)
    course.organisations.add(OrganisationFactory(name="Solo Academy"))

    assert "Solo Academy" in _row_lists(_dashboard_html())


@pytest.mark.django_db
def test_in_progress_row_names_the_organisation_the_learner_studies_through(
    mock_site_context, logged_in_client
):
    user = UserFactory()
    course = CourseFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user,
        learner__organisation=OrganisationFactory(name="Study Academy"),
        course=course,
    )
    course_progress_record(course, user)

    assert "Study Academy" in _row_lists(_dashboard_html(logged_in_client(user)))


@pytest.mark.django_db
def test_cards_name_nothing_for_the_default_organisation(
    mock_site_context, logged_in_client
):
    user = UserFactory()
    default = get_default_organisation(mock_site_context)
    default.name = "Home Academy"
    default.save(update_fields=["name"])
    CourseFactory().organisations.add(default)
    course = CourseFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user, learner__organisation=default, course=course
    )
    course_progress_record(course, user)

    assert "Home Academy" not in _dashboard_html(logged_in_client(user))


@pytest.mark.django_db
def test_card_byline_renders_the_monogram_when_the_organisation_has_no_logo(
    mock_site_context,
):
    CourseFactory(audience=CourseAudience.PUBLIC).organisations.add(
        OrganisationFactory(name="Plain Academy")
    )

    html = _dashboard_html()

    assert "Plain Academy" in html
    assert (
        "PA" in html.split('data-testid="organisation-byline"', 1)[1].split("</p>")[0]
    )


@pytest.mark.django_db
def test_card_byline_precedes_the_status_and_the_title(
    mock_site_context, logged_in_client
):
    CourseFactory(audience=CourseAudience.PUBLIC).organisations.add(
        OrganisationFactory(name="Plain Academy")
    )
    user = UserFactory()

    html = _dashboard_html(logged_in_client(user))

    byline = html.index('data-testid="organisation-byline"')
    assert byline < html.index('data-testid="course-status-')
    assert byline < html.index('<h3 class="wrap-break-word">')


@pytest.mark.django_db
def test_card_shell_article_has_no_zero_padding(mock_site_context):
    CourseFactory(audience=CourseAudience.PUBLIC)

    html = _dashboard_html()

    article = html.split('<article class="course-card', 1)[1].split(">", 1)[0]
    assert "p-0" not in article.split()


BYLINE_DASHBOARD_MAX_QUERIES = 48


@pytest.mark.django_db
def test_dashboard_query_count_does_not_grow_with_organisation_cards(
    mock_site_context, django_assert_max_num_queries, logged_in_client
):
    user = UserFactory()
    category = CourseCategoryFactory(show_on_dashboard=True)
    for _ in range(3):
        CourseFactory(
            dashboard_category=category, audience=CourseAudience.PUBLIC
        ).organisations.add(OrganisationFactory())
        CourseFactory(
            visibility=CourseVisibility.COMING_SOON, audience=CourseAudience.PUBLIC
        ).organisations.add(OrganisationFactory())
        RecommendedCourseFactory(
            user=user,
            course=_single_organisation_course(),
        )
    in_progress = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=in_progress)
    course_progress_record(in_progress, user)
    client = logged_in_client(user)

    with django_assert_max_num_queries(BYLINE_DASHBOARD_MAX_QUERIES):
        client.get(reverse("learner_interface:dashboard"))


def _single_organisation_course() -> Course:
    course: Course = CourseFactory(audience=CourseAudience.PUBLIC)
    course.organisations.add(OrganisationFactory())
    return course


@pytest.mark.django_db
def test_narrow_row_shows_the_byline_and_the_difficulty(mock_site_context):
    course = CourseFactory(audience=CourseAudience.PUBLIC, difficulty="intermediate")
    course.organisations.add(OrganisationFactory(name="Solo Academy"))

    row_lists = _row_lists(_dashboard_html())

    assert 'data-testid="organisation-byline"' in row_lists
    assert "Intermediate" in row_lists
