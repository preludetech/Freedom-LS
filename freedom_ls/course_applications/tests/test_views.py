"""Tests for course_applications views."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.student_management.factories import UserCourseRegistrationFactory

# ---------------------------------------------------------------------------
# apply view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApplyViewGet:
    """GET /apply/<slug>/ without an existing application — confirmation page."""

    def test_get_no_existing_app_returns_200(self, client, mock_site_context):
        """GET apply with no existing application renders a 200 confirmation page."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        assert response.status_code == 200

    def test_get_confirmation_page_contains_course_title(
        self, client, mock_site_context
    ):
        """GET apply confirmation page contains the course title."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        assert course.title in response.content.decode()

    def test_get_unauthenticated_redirects_to_login(self, client, mock_site_context):
        """GET apply without login redirects to login page."""
        course = CourseFactory()
        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_get_nonexistent_course_returns_404(self, client, mock_site_context):
        """GET apply for a non-existent course slug returns 404."""
        user = UserFactory()
        client.force_login(user)

        url = reverse(
            "course_applications:apply", kwargs={"course_slug": "no-such-course"}
        )
        response = client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestApplyViewGetExistingApplication:
    """GET /apply/<slug>/ when learner already has an application — redirect to status."""

    def test_get_with_existing_app_redirects_to_status(self, client, mock_site_context):
        """GET apply when learner has an existing application redirects to status page."""
        user = UserFactory()
        course = CourseFactory()
        existing_app = CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        expected_status_url = reverse(
            "course_applications:status", kwargs={"pk": existing_app.pk}
        )
        assert response.status_code == 302
        assert response["Location"] == expected_status_url

    def test_get_with_existing_app_does_not_create_duplicate(
        self, client, mock_site_context
    ):
        """GET apply when learner already applied does not create a duplicate application."""
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        client.get(url)

        assert CourseApplication.objects.filter(user=user, course=course).count() == 1


@pytest.mark.django_db
class TestApplyViewPost:
    """POST /apply/<slug>/ — creates application and redirects to status."""

    def test_post_creates_application(self, client, mock_site_context):
        """POST apply creates one CourseApplication for the learner."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        client.post(url)

        assert CourseApplication.objects.filter(user=user, course=course).count() == 1

    def test_post_redirects_to_status_page(self, client, mock_site_context):
        """POST apply redirects to the application status page."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.post(url)

        app = CourseApplication.objects.get(user=user, course=course)
        expected_status_url = reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )
        assert response.status_code == 302
        assert response["Location"] == expected_status_url

    def test_second_post_does_not_create_duplicate(self, client, mock_site_context):
        """A second POST to apply for the same course does not create a duplicate."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        client.post(url)
        client.post(url)

        assert CourseApplication.objects.filter(user=user, course=course).count() == 1

    def test_second_post_redirects_to_existing_status(self, client, mock_site_context):
        """A second POST redirects to the same existing application status page."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        client.post(url)
        response = client.post(url)

        app = CourseApplication.objects.get(user=user, course=course)
        expected_status_url = reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )
        assert response.status_code == 302
        assert response["Location"] == expected_status_url


@pytest.mark.django_db
class TestApplyViewVisibilityGate:
    """apply enforces course visibility (hidden means hidden; coming-soon not enrollable)."""

    def _apply_url(self, course):
        return reverse("course_applications:apply", kwargs={"course_slug": course.slug})

    def test_hidden_unregistered_get_returns_404(self, client, mock_site_context):
        """GET apply for a hidden course by an unregistered user 404s (no existence leak)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        client.force_login(user)

        response = client.get(self._apply_url(course))

        assert response.status_code == 404

    def test_hidden_unregistered_post_does_not_create_application(
        self, client, mock_site_context
    ):
        """POST apply for a hidden course by an unregistered user 404s and creates nothing."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        client.force_login(user)

        response = client.post(self._apply_url(course))

        assert response.status_code == 404
        assert not CourseApplication.objects.filter(user=user, course=course).exists()

    def test_hidden_registered_get_returns_200(self, client, mock_site_context):
        """A registered learner still reaches the apply page for a hidden course."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        client.force_login(user)

        response = client.get(self._apply_url(course))

        assert response.status_code == 200

    def test_coming_soon_post_redirects_to_detail_and_creates_nothing(
        self, client, mock_site_context
    ):
        """POST apply for a coming-soon course redirects to detail without applying."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        response = client.post(self._apply_url(course))

        expected = reverse(
            "student_interface:course_detail", kwargs={"course_slug": course.slug}
        )
        assert response.status_code == 302
        assert response["Location"] == expected
        assert not CourseApplication.objects.filter(user=user, course=course).exists()


# ---------------------------------------------------------------------------
# application_status view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApplicationStatusView:
    """Applicant status page."""

    def test_owner_gets_200(self, client, mock_site_context):
        """Application owner receives a 200 status page."""
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        assert response.status_code == 200

    def test_status_page_contains_pending_review_message(
        self, client, mock_site_context
    ):
        """Status page contains the pending-review confirmation message."""
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        content = response.content.decode()
        # The page must mention that the application has been received
        assert "received" in content.lower() or "pending" in content.lower()

    def test_non_owner_gets_404(self, client, mock_site_context):
        """A learner who does not own the application gets 404."""
        owner = UserFactory()
        other_user = UserFactory()
        app = CourseApplicationFactory(user=owner)
        client.force_login(other_user)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        assert response.status_code == 404

    def test_unauthenticated_redirects_to_login(self, client, mock_site_context):
        """Unauthenticated access to status page redirects to login."""
        owner = UserFactory()
        app = CourseApplicationFactory(user=owner)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        assert response.status_code == 302
        assert "/accounts/" in response["Location"]
