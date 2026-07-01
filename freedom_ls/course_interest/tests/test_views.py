"""Tests for course_interest views (Task 3.1 + Task 3.2).

TDD: these tests are written before the implementation.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.student_management.factories import UserCourseRegistrationFactory

# ---------------------------------------------------------------------------
# express_interest view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpressInterestCreatesRow:
    """POST express_interest on a coming-soon course creates exactly one row."""

    def test_post_coming_soon_creates_interest_row(self, client, mock_site_context):
        """POST express_interest on a coming-soon course creates a CourseInterest row."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        client.post(url, HTTP_HX_REQUEST="true")

        assert CourseInterest.objects.filter(user=user, course=course).count() == 1

    def test_second_post_is_no_op(self, client, mock_site_context):
        """A second POST to express_interest is a no-op (still exactly one row)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        client.post(url, HTTP_HX_REQUEST="true")
        client.post(url, HTTP_HX_REQUEST="true")

        assert CourseInterest.objects.filter(user=user, course=course).count() == 1

    def test_post_coming_soon_renders_interested_state(self, client, mock_site_context):
        """POST express_interest on a coming-soon course renders the interested state."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        content = response.content.decode()
        assert response.status_code == 200
        assert "Interested" in content


@pytest.mark.django_db
class TestExpressInterestOnPublishedCourse:
    """POST express_interest on a published course returns 422 and creates no row."""

    def test_post_published_course_returns_422(self, client, mock_site_context):
        """POST express_interest on a published course returns HTTP 422."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.PUBLISHED)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 422

    def test_post_published_course_creates_no_row(self, client, mock_site_context):
        """POST express_interest on a published course does not create a CourseInterest row."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.PUBLISHED)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        client.post(url, HTTP_HX_REQUEST="true")

        assert CourseInterest.objects.filter(user=user, course=course).count() == 0


@pytest.mark.django_db
class TestExpressInterestOnHiddenCourse:
    """POST express_interest on a hidden course 404s for unregistered users.

    A hidden course must never confirm its existence (spec §13) — so it returns
    404, not the distinguishable 422 a published course returns.
    """

    def test_post_hidden_unregistered_returns_404(self, client, mock_site_context):
        """POST express_interest on a hidden course by an unregistered user returns 404."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 404
        assert CourseInterest.objects.filter(user=user, course=course).count() == 0

    def test_post_hidden_registered_returns_422(self, client, mock_site_context):
        """A registered learner on a hidden (non-coming-soon) course gets the 422 no-op."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# remove_interest view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRemoveInterest:
    """POST remove_interest deletes the row if present, no-op if absent."""

    def test_remove_interest_deletes_row(self, client, mock_site_context):
        """POST remove_interest deletes the CourseInterest row."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseInterestFactory(user=user, course=course)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        client.post(url, HTTP_HX_REQUEST="true")

        assert CourseInterest.objects.filter(user=user, course=course).count() == 0

    def test_remove_interest_no_op_when_absent(self, client, mock_site_context):
        """POST remove_interest when no row exists is a no-op (no error)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 200

    def test_remove_interest_renders_not_interested_state(
        self, client, mock_site_context
    ):
        """POST remove_interest renders the not-interested state of the CTA."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseInterestFactory(user=user, course=course)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        content = response.content.decode()
        assert response.status_code == 200
        assert "I'm interested" in content


# ---------------------------------------------------------------------------
# GET rejected (POST-only)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpressInterestGetRejected:
    """GET on express_interest and remove_interest endpoints is rejected."""

    def test_get_express_interest_rejected(self, client, mock_site_context):
        """GET express_interest is rejected (method not allowed)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.get(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 405

    def test_get_remove_interest_rejected(self, client, mock_site_context):
        """GET remove_interest is rejected (method not allowed)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.get(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 405


# ---------------------------------------------------------------------------
# Anonymous user redirected through login
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpressInterestAnonymousRedirect:
    """Anonymous users are redirected to the login page."""

    def test_anonymous_express_interest_redirects_to_login(
        self, client, mock_site_context
    ):
        """Anonymous POST to express_interest redirects to login."""
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_anonymous_remove_interest_redirects_to_login(
        self, client, mock_site_context
    ):
        """Anonymous POST to remove_interest redirects to login."""
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 302
        assert "/accounts/" in response["Location"]


# ---------------------------------------------------------------------------
# Task 3.2: content assertions (success criterion 7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpressInterestCTAContent:
    """The interested-state CTA must NOT promise a notification (spec §7.2, §10)."""

    def test_interested_state_contains_no_notification_promise(
        self, client, mock_site_context
    ):
        """The interested-state response does not contain notification-promising strings."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        content = response.content.decode().lower()
        assert "email" not in content
        assert "notify" not in content
        assert "notification" not in content
        assert "we'll let you know" not in content
