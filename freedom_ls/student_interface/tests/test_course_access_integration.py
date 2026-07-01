"""Tests for wiring the course-access backend into student_interface.

Covers:
1. Chokepoint gate in initiate_course_access
2. CTA branching in course_detail
3. Listing visibility (filter_visible)
4. Content-access gate (view_course_item, get_course_index, course_home)
5. Dashboard contributions (plugin dashboard seam)

These tests import course_applications factories/models to *build state* but
student_interface production code must NOT import course_applications — that rule
is enforced by the architecture, not these tests.
"""

from __future__ import annotations

import pytest

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.student_interface.utils import BLOCKED
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_management.models import UserCourseRegistration
from freedom_ls.student_progress.factories import CourseProgressFactory

# ---------------------------------------------------------------------------
# 1. Chokepoint gate — initiate_course_access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_initiate_access_gated_course_redirects_to_apply_url(
    mock_site_context, logged_in_client, course_with_topic
):
    """POST initiate_course_access for a gated course redirects to the apply URL."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.post(url)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    assert response.status_code == 302
    assert response["Location"] == apply_url


@pytest.mark.django_db
def test_initiate_access_gated_course_creates_no_registration(
    mock_site_context, logged_in_client, course_with_topic
):
    """POST initiate_course_access for a gated course does NOT create a UserCourseRegistration."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    client.post(url)

    assert not UserCourseRegistration.objects.filter(
        user=user, collection=course
    ).exists()


@pytest.mark.django_db
def test_initiate_access_gated_course_get_also_redirects(
    mock_site_context, logged_in_client, course_with_topic
):
    """GET initiate_course_access for a gated course also redirects (no self-register)."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    assert response.status_code == 302
    assert response["Location"] == apply_url


@pytest.mark.django_db
def test_initiate_access_free_course_creates_registration(
    mock_site_context, logged_in_client, course_with_topic
):
    """POST initiate_course_access for a free course creates a UserCourseRegistration."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    client.post(url)

    assert UserCourseRegistration.objects.filter(user=user, collection=course).exists()


# ---------------------------------------------------------------------------
# 2. CTA branching — course_detail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_detail_gated_not_registered_shows_apply_now(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a gated course with an unregistered learner shows 'Apply now'."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    body = response.content.decode()
    assert "Apply now" in body


@pytest.mark.django_db
def test_course_detail_gated_not_registered_cta_url_is_apply_url(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a gated course: start_url points to the apply view."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    assert apply_url in response.content.decode()


@pytest.mark.django_db
def test_course_detail_free_not_registered_shows_enrol_for_free_label(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a free course with an unregistered learner shows the backend's free label."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    # The FreeOnlyCourseAccessBackend label for a free unregistered learner
    assert "Enrol for free" in response.content.decode()


@pytest.mark.django_db
def test_course_detail_gated_shows_application_copy_not_free_copy(
    mock_site_context, logged_in_client, course_with_topic
):
    """The gated detail page must show application funnel copy, not the free copy.

    The funnel copy (enrolment summary, sign-up heading/subtext) is driven by the
    access backend, so a gated course must not claim to be "Free · open" / "One
    click. No credit card." alongside its "Apply now" CTA.
    """
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert "Free · open" not in body
    assert "One click. No credit card." not in body
    assert "By application" in body
    assert "Application required" in body
    assert "Apply and we&#x27;ll review your request." in body


@pytest.mark.django_db
def test_course_detail_free_shows_free_acquisition_copy(
    mock_site_context, logged_in_client, course_with_topic
):
    """The free detail page still shows the free funnel copy (driven by the backend)."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert "Free · open" in body
    assert "One click. No credit card." in body


@pytest.mark.django_db
def test_course_detail_registered_shows_start_course_label(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a registered learner with 0 progress shows 'Start course'."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Start course" in response.content.decode()


@pytest.mark.django_db
def test_course_detail_registered_in_progress_shows_continue_label(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a registered learner with progress shows 'Continue'."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    CourseProgressFactory(user=user, course=course, progress_percentage=50)
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Continue" in response.content.decode()


@pytest.mark.django_db
def test_course_detail_registered_completed_shows_review_label(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a registered and completed learner shows 'Review course'."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    CourseProgressFactory(
        user=user,
        course=course,
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Review course" in response.content.decode()


# ---------------------------------------------------------------------------
# 3. Listing visibility
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_lists_all_courses_with_default_backend(
    mock_site_context, logged_in_client
):
    """With the default backend, available_courses set is unchanged (filter_visible is a no-op)."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))

    assert response.status_code == 200
    available = response.context["available_courses"]
    available_ids = {c.id for c in available}
    assert course_a.id in available_ids
    assert course_b.id in available_ids


# ---------------------------------------------------------------------------
# 4. Content-access gate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_view_course_item_unregistered_redirects_to_course_detail(
    mock_site_context, logged_in_client, course_with_topic
):
    """view_course_item for an unregistered learner redirects to course_detail."""
    course = course_with_topic(access_type="free")
    user = UserFactory()  # not registered
    client = logged_in_client(user)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_view_course_item_registered_renders_content(
    mock_site_context, logged_in_client, course_with_topic
):
    """view_course_item for a registered learner renders the content (not a redirect)."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    client = logged_in_client(user)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_course_detail_unregistered_all_toc_items_blocked(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for an unregistered learner shows all TOC items as BLOCKED."""

    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    children = response.context["children"]
    assert children  # at least one item exists
    assert all(child["status"] == BLOCKED for child in children)


@pytest.mark.django_db
def test_course_detail_registered_toc_items_not_all_blocked(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a registered learner has at least one non-BLOCKED TOC item."""

    course = course_with_topic(access_type="free")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    children = response.context["children"]
    assert children
    statuses = [child["status"] for child in children]
    assert any(s != BLOCKED for s in statuses)


@pytest.mark.django_db
def test_course_home_unregistered_redirects_to_course_detail(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_home for an unregistered learner redirects to course_detail."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse("student_interface:course_home", kwargs={"course_slug": course.slug})
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_gated_course_detail_unregistered_shows_apply_not_item_content(
    mock_site_context, logged_in_client, course_with_topic
):
    """course_detail for a gated course: unregistered learner sees Apply affordance and blocked items."""

    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    body = response.content.decode()
    assert "Apply now" in body
    # All TOC items must be blocked
    children = response.context["children"]
    assert all(child["status"] == BLOCKED for child in children)


@pytest.mark.django_db
def test_view_course_item_gated_unregistered_redirects_to_course_detail(
    mock_site_context, logged_in_client, course_with_topic
):
    """view_course_item for a gated course with an unregistered learner redirects to course_detail."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )


# ---------------------------------------------------------------------------
# 5. Dashboard contributions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_with_active_application_shows_status_link(
    mock_site_context, logged_in_client, course_with_topic
):
    """Dashboard shows the status link for an in-flight application (via ApplicationCourseAccessBackend)."""
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    application = CourseApplicationFactory(user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))

    assert response.status_code == 200
    body = response.content.decode()
    status_url = reverse("course_applications:status", kwargs={"pk": application.pk})
    assert status_url in body


@pytest.mark.django_db
def test_dashboard_without_applications_shows_no_extra_panel(
    mock_site_context, logged_in_client
):
    """Dashboard with no active applications shows no application panel.

    Uses FreeOnlyCourseAccessBackend (which returns [] for get_dashboard_contributions)
    to isolate this test from any active applications that might exist on the site.
    The autouse _clear_course_access_backend_cache fixture clears before/after each
    test; we also clear inside the override_settings context to ensure the override
    takes effect within this test body.
    """
    user = UserFactory()
    client = logged_in_client(user)

    with override_settings(
        COURSE_ACCESS_BACKEND="freedom_ls.course_access.backends.FreeOnlyCourseAccessBackend"
    ):
        get_course_access_backend.cache_clear()
        response = client.get(reverse("student_interface:dashboard"))

    assert response.status_code == 200
    assert "dashboard_panels" in response.context
    assert response.context["dashboard_panels"] == []


@pytest.mark.django_db
def test_dashboard_panels_in_context(mock_site_context, logged_in_client):
    """The dashboard view always includes dashboard_panels in context."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))

    assert response.status_code == 200
    assert "dashboard_panels" in response.context


# ---------------------------------------------------------------------------
# Visibility chokepoints — hidden 404s, coming-soon routing
# ---------------------------------------------------------------------------


def _hidden_course() -> Course:
    """Create a hidden course with one viewable topic."""
    course: Course = CourseFactory(
        slug="hidden-course", title="Hidden Course", visibility=CourseVisibility.HIDDEN
    )
    topic = TopicFactory(title="Topic 1", slug="hidden-topic-1", content="content")
    course.items.create(child=topic, order=0)
    return course


def _coming_soon_course() -> Course:
    """Create a coming-soon course with one viewable topic."""
    course: Course = CourseFactory(
        slug="coming-soon-course",
        title="Coming Soon Course",
        visibility=CourseVisibility.COMING_SOON,
    )
    topic = TopicFactory(title="Topic 1", slug="cs-topic-1", content="content")
    course.items.create(child=topic, order=0)
    return course


@pytest.mark.django_db
def test_course_home_hidden_unregistered_returns_404(mock_site_context):
    """course_home for a hidden course must 404 for an unregistered user, not 302."""
    course = _hidden_course()
    client = _client(UserFactory())

    url = reverse("student_interface:course_home", kwargs={"course_slug": course.slug})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_course_home_hidden_registered_still_resolves(mock_site_context):
    """A registered learner still reaches course_home for a hidden course (redirects into player)."""
    course = _hidden_course()
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
    client = _client(user)

    url = reverse("student_interface:course_home", kwargs={"course_slug": course.slug})
    response = client.get(url)

    assert response.status_code == 302


@pytest.mark.django_db
def test_view_course_item_hidden_unregistered_returns_404(mock_site_context):
    """view_course_item for a hidden course must 404 for an unregistered user, not 302."""
    course = _hidden_course()
    client = _client(UserFactory())

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_view_course_item_hidden_registered_renders_content(mock_site_context):
    """A registered learner still views content of a hidden course."""
    course = _hidden_course()
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
    client = _client(user)

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_initiate_access_coming_soon_redirects_to_detail(mock_site_context):
    """POST initiate_course_access for a coming-soon course redirects to the detail page.

    The coming-soon CTA url is the POST-only express-interest endpoint; redirecting
    the browser (GET) there would 405. The safe fallback is the detail page.
    """
    course = _coming_soon_course()
    client = _client(UserFactory())

    url = reverse(
        "student_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.post(url)

    detail_url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    assert response.status_code == 302
    assert response["Location"] == detail_url


@pytest.mark.django_db
def test_initiate_access_coming_soon_creates_no_registration(mock_site_context):
    """initiate_course_access for a coming-soon course does not self-register the learner."""
    course = _coming_soon_course()
    user = UserFactory()
    client = _client(user)

    url = reverse(
        "student_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    client.post(url)

    assert not UserCourseRegistration.objects.filter(
        user=user, collection=course
    ).exists()


@pytest.mark.django_db
def test_initiate_access_hidden_unregistered_returns_404(mock_site_context):
    """initiate_course_access for a hidden course 404s for an unregistered user."""
    course = _hidden_course()
    client = _client(UserFactory())

    url = reverse(
        "student_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.post(url)

    assert response.status_code == 404
