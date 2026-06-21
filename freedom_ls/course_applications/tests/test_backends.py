"""Tests for ApplicationCourseAccessBackend (Task B.6).

TDD: failing tests written first, then implementation added.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.factories import CourseApplicationFactory

APPLICATION_BACKEND = (
    "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)


@pytest.fixture(autouse=True)
def _clear_backend_cache():
    from freedom_ls.course_access.loader import get_course_access_backend

    get_course_access_backend.cache_clear()
    yield
    get_course_access_backend.cache_clear()


@pytest.mark.django_db
class TestValidateCourseConfig:
    """Task B.6 — validate_course_config on ApplicationCourseAccessBackend."""

    def test_application_gated_is_accepted(self, mock_site_context):
        """validate_course_config accepts access_type=application_gated."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        result = backend.validate_course_config({"access_type": "application_gated"})
        assert result == {"access_type": "application_gated"}

    def test_free_is_accepted(self, mock_site_context):
        """validate_course_config accepts access_type=free (inherited from parent)."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        result = backend.validate_course_config({"access_type": "free"})
        assert result == {"access_type": "free"}

    def test_absent_access_type_defaults_to_free(self, mock_site_context):
        """validate_course_config with absent access_type defaults to free."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        result = backend.validate_course_config({})
        assert result["access_type"] == "free"

    def test_unknown_access_type_raises_value_error(self, mock_site_context):
        """validate_course_config rejects an unknown access_type value."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        with pytest.raises(ValueError, match="invalid access_type"):
            backend.validate_course_config({"access_type": "subscription"})

    def test_unknown_key_raises_value_error(self, mock_site_context):
        """validate_course_config rejects unknown keys."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        with pytest.raises(ValueError, match="unknown key"):
            backend.validate_course_config({"unknown_key": "value"})

    def test_file_path_included_in_error_message(self, mock_site_context):
        """ValueError for invalid config includes the file_path context."""
        import re

        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        with pytest.raises(ValueError, match=re.escape("some/file.yaml")):
            backend.validate_course_config(
                {"access_type": "bad_value"}, file_path="some/file.yaml"
            )


@pytest.mark.django_db
class TestGetAccess:
    """Task B.6 — get_access on ApplicationCourseAccessBackend."""

    def test_application_gated_course_returns_apply_now_cta(self, mock_site_context):
        """get_access for an application-gated course returns 'Apply now' CTA."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Apply now"

    def test_application_gated_cta_url_points_to_apply_view(self, mock_site_context):
        """get_access for application-gated course CTA URL points to apply view."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        expected_url = reverse(
            "course_applications:apply", kwargs={"course_slug": course.slug}
        )
        assert decision.cta_url == expected_url

    def test_application_gated_cannot_self_register(self, mock_site_context):
        """get_access for application-gated course sets can_self_register=False."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.can_self_register is False

    def test_application_gated_cannot_access_content(self, mock_site_context):
        """get_access for application-gated course sets can_access_content=False."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.can_access_content is False

    def test_registered_learner_on_gated_course_gets_content(self, mock_site_context):
        """A learner enrolled into a gated course (admin/cohort) bypasses the gate.

        Spec §3: admin/cohort enrolment deliberately bypasses the application
        gate, so a registered learner reaches content (Continue/can_access_content)
        rather than being told to "Apply now".
        """
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )
        from freedom_ls.student_management.factories import (
            UserCourseRegistrationFactory,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Continue"
        assert decision.can_access_content is True
        assert decision.can_self_register is False

    def test_free_course_returns_start_cta(self, mock_site_context):
        """get_access for free course returns 'Start' CTA (inherited from parent)."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "free"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Start"
        assert decision.can_self_register is True


@pytest.mark.django_db
class TestGetDashboardContributions:
    """Task B.6 — get_dashboard_contributions on ApplicationCourseAccessBackend."""

    def test_returns_one_contribution_when_learner_has_active_application(
        self, mock_site_context
    ):
        """get_dashboard_contributions returns one contribution for a learner with an application."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        CourseApplicationFactory(user=user)

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=user)

        assert len(contributions) == 1

    def test_contribution_template_is_dashboard_applications_partial(
        self, mock_site_context
    ):
        """The contribution uses the dashboard_applications partial template."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        CourseApplicationFactory(user=user)

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=user)

        assert (
            contributions[0].template_name
            == "course_applications/partials/dashboard_applications.html"
        )

    def test_contribution_context_contains_applications(self, mock_site_context):
        """The contribution context includes the learner's applications."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        app = CourseApplicationFactory(user=user)

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=user)
        apps = list(contributions[0].context["applications"])

        assert app in apps

    def test_returns_empty_list_when_no_applications(self, mock_site_context):
        """get_dashboard_contributions returns empty list when learner has no applications."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=user)

        assert contributions == []


@pytest.mark.django_db
class TestDashboardPartialRendering:
    """Task B.6 — the dashboard_applications partial renders status links."""

    def test_partial_renders_status_link(self, client, mock_site_context):
        """Dashboard applications partial renders a link to the application status page."""
        from django.template.loader import render_to_string

        user = UserFactory()
        app = CourseApplicationFactory(user=user)

        expected_url = reverse("course_applications:status", kwargs={"pk": app.pk})
        rendered = render_to_string(
            "course_applications/partials/dashboard_applications.html",
            {"applications": [app]},
        )

        assert expected_url in rendered
