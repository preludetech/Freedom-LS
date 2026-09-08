"""Query-cost regression tests for the dashboard.

The In progress and category-section builders run one access-decision lookup
and one player-index build per course (`_annotate_registered_courses`,
`_annotate_discovery_courses`), so a per-course query pinned to unbounded
registration or category growth would defeat the pagination that Step 6 was
built to cap. Each test below pins a section's query count against a
realistic-sized page and then grows the input that section must not be
sensitive to, to prove the count held.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseCategoryFactory, CourseFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

IN_PROGRESS_MAX_QUERIES = 58
CATEGORY_SECTION_MAX_QUERIES = 6


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
