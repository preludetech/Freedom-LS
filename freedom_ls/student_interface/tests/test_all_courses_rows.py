"""Tests for the rendered HTML of all_courses rows.

These assert on the markup the all_courses page produces for each
registration state: status labels, preview/link affordances, progress-bar
presence and value, and decorative status icons. The context-level
status/annotation logic is covered in ``test_all_courses_view``.
"""

from __future__ import annotations

import re

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_progress.factories import CourseProgressFactory


def _coming_soon_course(*, slug: str, title: str) -> Course:
    """A coming-soon-visibility course with one topic item."""
    course: Course = CourseFactory(
        title=title, slug=slug, visibility=CourseVisibility.COMING_SOON
    )
    topic = TopicFactory(title=f"{slug}-t", slug=f"{slug}-topic", content="content")
    course.items.create(child=topic, order=0)
    return course


@pytest.mark.django_db
def test_all_courses_renders_four_distinct_status_labels(
    mock_site_context, courses, logged_in_client
):
    """Each of the four registration states renders its own visible label, so a
    registered-but-unstarted course is no longer indistinguishable from an
    unregistered one. The old ambiguous "Not started" label is gone entirely."""
    user = UserFactory()
    # courses[0] -> Not registered (left unregistered)
    # courses[1] -> Registered (enrolled, 0% progress)
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    # courses[2] -> In progress (enrolled, >0% progress)
    UserCourseRegistrationFactory(user=user, collection=courses[2])
    CourseProgressFactory(
        user=user, course=courses[2], progress_percentage=40, completed_time=None
    )
    # A fourth course -> Completed.
    completed = CourseFactory(title="Course D", slug="course-d")
    completed_topic = TopicFactory(title="Topic D", slug="topic-d", content="content")
    completed.items.create(child=completed_topic, order=0)
    UserCourseRegistrationFactory(user=user, collection=completed)
    CourseProgressFactory(
        user=user,
        course=completed,
        progress_percentage=100,
        completed_time=timezone.now(),
    )

    client = logged_in_client(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()

    assert "Not registered" in body
    assert "Registered" in body  # the registered-0% row (capital R, standalone)
    assert "In progress" in body
    assert "Completed" in body
    assert "Not started" not in body  # retired ambiguous label


@pytest.mark.django_db
def test_all_courses_not_registered_row_links_to_course_detail(
    mock_site_context, courses, logged_in_client
):
    """A not-registered course row renders a single link to the course_detail URL."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "student_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert detail_url in body


@pytest.mark.django_db
def test_all_courses_not_registered_row_has_no_progress_bar(
    mock_site_context, courses, logged_in_client
):
    """A not-registered course row does not render a progress bar."""
    user = UserFactory()
    # No registration — courses[0] is NOT_REGISTERED
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    # The progress bar element is only present for registered/in-progress rows.
    # Locate the not-registered course section by its title and confirm no <progress>
    # appears in the page for the not-registered row.
    # (A simple check: if no courses are registered, NO progress bars exist.)
    assert "<progress" not in body


@pytest.mark.django_db
def test_all_courses_registered_zero_percent_row_links_to_first_item(
    mock_site_context, courses, logged_in_client
):
    """A registered-0% row links to view_course_item at index=1."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    item_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": courses[0].slug, "index": 1},
    )
    body = response.content.decode()
    assert item_url in body


@pytest.mark.django_db
def test_all_courses_registered_zero_percent_row_has_progress_value_zero(
    mock_site_context, courses, logged_in_client
):
    """A registered-0% row renders a progress bar reporting value='0'.

    The shared <c-course-progress-bar> uses a native <progress>, which exposes
    its value to assistive tech via the value attribute (implicit progressbar
    role) rather than an explicit aria-valuenow.
    """
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert "<progress" in body
    assert 'value="0"' in body


@pytest.mark.django_db
def test_all_courses_in_progress_row_links_to_first_item(
    mock_site_context, courses, logged_in_client
):
    """An in-progress row links to view_course_item at index=1."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=55, completed_time=None
    )
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    item_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": courses[0].slug, "index": 1},
    )
    body = response.content.decode()
    assert item_url in body


@pytest.mark.django_db
def test_all_courses_in_progress_row_has_progress_value_above_zero(
    mock_site_context, courses, logged_in_client
):
    """An in-progress row renders a progress bar reporting its percentage as value.

    The shared <c-course-progress-bar> uses a native <progress>, whose value
    attribute carries the percentage to assistive tech.
    """
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=55, completed_time=None
    )
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert "<progress" in body
    assert 'value="55"' in body


@pytest.mark.django_db
def test_all_courses_complete_row_links_to_course_finish(
    mock_site_context, courses, logged_in_client
):
    """A completed-course row links to the course_finish URL."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user,
        course=courses[0],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    finish_url = reverse(
        "student_interface:course_finish",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert finish_url in body


@pytest.mark.django_db
def test_all_courses_complete_row_has_no_progress_bar(
    mock_site_context, courses, logged_in_client
):
    """A completed-course row does not render a progress bar."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user,
        course=courses[0],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    # Register and complete only courses[0]; courses[1] and [2] remain unregistered.
    # No registered-but-incomplete courses means no progress bars in the whole page.
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert "<progress" not in body


@pytest.mark.django_db
def test_all_courses_status_icons_are_decorative(
    mock_site_context, courses, logged_in_client
):
    """Status icons are decorative: the icon backend always stamps the semantic
    slug as the svg's aria-label, so each status icon must be wrapped in an
    `aria-hidden="true"` element to keep that slug out of the accessibility tree.
    Status is conveyed by the adjacent visible text (WCAG 1.4.1), never the slug.
    """
    user = UserFactory()
    # In-progress and complete rows exercise the in_progress/complete icons.
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=40, completed_time=None
    )
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    CourseProgressFactory(
        user=user,
        course=courses[1],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    # courses[2] stays unregistered -> exercises the not_started icon.
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    # Every status-icon svg (which carries aria-label="<slug>") must sit directly
    # inside an aria-hidden wrapper.
    for slug in ("in_progress", "not_started", "complete"):
        assert f'aria-label="{slug}"' in body, f"expected {slug} icon to render"
        assert re.search(
            rf'aria-hidden="true">\s*<svg[^>]*aria-label="{slug}"', body
        ), f"status icon {slug!r} is not wrapped in aria-hidden"


@pytest.mark.django_db
def test_all_courses_registered_row_has_details_link(
    mock_site_context, courses, logged_in_client
):
    """A registered (0%) row renders an explicit "Details" link to course_detail,
    in addition to the progress-linked title."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "student_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_complete_row_has_details_link(
    mock_site_context, courses, logged_in_client
):
    """A completed-course row renders an explicit "Details" link to course_detail,
    in addition to the finish-page title link."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user,
        course=courses[0],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "student_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_not_registered_row_has_details_link(
    mock_site_context, courses, logged_in_client
):
    """A not-registered row renders an explicit "Details" link in addition to
    the stretched title link — both resolve to the same course_detail URL."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "student_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_coming_soon_row_has_details_link(mock_site_context):
    """A coming-soon row renders an explicit "Details" link alongside the
    "Coming soon" status eyebrow, in addition to the stretched title link."""
    course = _coming_soon_course(slug="cs-row", title="Coming Soon Row Course")
    client = Client()

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_details_link_renders_for_anonymous_visitor(
    mock_site_context, courses
):
    """The Details link renders on the all-courses page for an anonymous
    visitor, not just for authenticated ones."""
    client = Client()

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "student_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body


@pytest.mark.django_db
def test_all_courses_details_link_renders_for_authenticated_unregistered_visitor(
    mock_site_context, courses, logged_in_client
):
    """The Details link renders for an authenticated visitor with no
    registration for the course."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    detail_url = reverse(
        "student_interface:course_detail",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert "Details" in body
    assert f'href="{detail_url}"' in body
