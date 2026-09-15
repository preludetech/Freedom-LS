"""How the dashboard's discovery pool splits into sections.

Only ``Course.dashboard_category`` decides where a course lands: the other
categories a course belongs to are deliberately never consulted here. A
coming-soon course is the one exception to "one course, one section". It
renders in Coming soon and, if its dashboard category is shown, in that
category's section too.
"""

from __future__ import annotations

import pytest

from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseCategoryFactory, CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

from .conftest import (
    course_progress_record,
    rendered_section,
    section_by_slug,
)


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
