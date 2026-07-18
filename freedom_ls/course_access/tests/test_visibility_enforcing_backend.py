"""Tests for VisibilityEnforcingBackend and loader wrapping.

Parametrised over both FreeOnlyCourseAccessBackend and ApplicationCourseAccessBackend
to prove enforcement is structural (the wrapper, not the inner backend).
"""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)

BACKEND_PATHS = [
    "freedom_ls.course_access.backends.FreeOnlyCourseAccessBackend",
    "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend",
]


def _decision_for(backend_path, *, user, course):
    """Resolve the configured backend and return its access decision."""
    with override_settings(COURSE_ACCESS_BACKEND=backend_path):
        get_course_access_backend.cache_clear()
        return get_course_access_backend().get_access(user=user, course=course)


def _filter_visible_for(backend_path, *, user, courses):
    """Resolve the configured backend and return its filtered queryset."""
    with override_settings(COURSE_ACCESS_BACKEND=backend_path):
        get_course_access_backend.cache_clear()
        return get_course_access_backend().filter_visible(user=user, courses=courses)


def _backend_for(backend_path):
    """Resolve the configured (visibility-wrapped) backend instance."""
    with override_settings(COURSE_ACCESS_BACKEND=backend_path):
        get_course_access_backend.cache_clear()
        return get_course_access_backend()


@pytest.mark.django_db
@pytest.mark.parametrize("backend_path", BACKEND_PATHS)
class TestVisibilityEnforcingBackendGetAccess:
    """VisibilityEnforcingBackend.get_access — parametrised over both inner backends."""

    def test_coming_soon_cannot_access_content(self, mock_site_context, backend_path):
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        decision = _decision_for(backend_path, user=UserFactory(), course=course)

        assert decision.can_access_content is False

    def test_coming_soon_cannot_self_register(self, mock_site_context, backend_path):
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        decision = _decision_for(backend_path, user=UserFactory(), course=course)

        assert decision.can_self_register is False

    def test_coming_soon_cta_label_is_interested(self, mock_site_context, backend_path):
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        decision = _decision_for(backend_path, user=UserFactory(), course=course)

        assert decision.cta_label == "I'm interested"

    def test_coming_soon_cta_url_resolves_to_express_interest(
        self, mock_site_context, backend_path
    ):
        course = CourseFactory(
            slug="my-coming-course", visibility=CourseVisibility.COMING_SOON
        )
        decision = _decision_for(backend_path, user=UserFactory(), course=course)

        expected_url = reverse(
            "course_interest:express_interest",
            kwargs={"course_slug": "my-coming-course"},
        )
        assert decision.cta_url == expected_url

    def test_coming_soon_funnel_copy_is_coming_soon(
        self, mock_site_context, backend_path
    ):
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        decision = _decision_for(backend_path, user=UserFactory(), course=course)

        assert decision.enrolment_summary == "Coming soon"
        assert decision.acquisition_heading == "Coming soon"

    def test_coming_soon_acquisition_subtext_does_not_promise_email_notification(
        self, mock_site_context, backend_path
    ):
        """Funnel copy must not promise an email/notification channel."""
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        decision = _decision_for(backend_path, user=UserFactory(), course=course)

        subtext = (decision.acquisition_subtext or "").lower()
        assert "email" not in subtext
        assert "notify" not in subtext
        assert "notification" not in subtext

    def test_hidden_unregistered_is_fully_closed(self, mock_site_context, backend_path):
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        decision = _decision_for(backend_path, user=UserFactory(), course=course)

        assert decision.can_access_content is False
        assert decision.can_self_register is False
        assert decision.cta_label is None
        assert decision.cta_url is None

    def test_hidden_registered_delegates_to_inner(
        self, mock_site_context, backend_path
    ):
        """A registered user on a hidden course gets content access (delegated)."""
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        decision = _decision_for(backend_path, user=user, course=course)

        assert decision.can_access_content is True

    def test_coming_soon_registered_delegates_to_inner(
        self, mock_site_context, backend_path
    ):
        """A registered user on a coming-soon course keeps content access (delegated).

        coming_soon exempts already-registered learners, mirroring hidden — a
        visibility change never disrupts a mid-course learner.
        """
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        decision = _decision_for(backend_path, user=user, course=course)

        assert decision.can_access_content is True
        # The express-interest CTA never reaches a registered learner.
        assert decision.cta_label != "I'm interested"

    def test_published_delegates_to_inner_start_cta(
        self, mock_site_context, backend_path
    ):
        course = CourseFactory(
            visibility=CourseVisibility.PUBLISHED,
            access_config={"access_type": "free"},
        )
        decision = _decision_for(backend_path, user=UserFactory(), course=course)

        # Both inner backends give the free acquisition CTA for an unregistered
        # learner on a free course; the wrapper delegates unchanged.
        assert decision.cta_label == "Enrol for free"
        assert decision.can_self_register is True


@pytest.mark.django_db
@pytest.mark.parametrize("backend_path", BACKEND_PATHS)
class TestVisibilityEnforcingBackendFilterVisible:
    """VisibilityEnforcingBackend.filter_visible — parametrised over both inner backends."""

    def test_hidden_course_excluded_for_anonymous(
        self, mock_site_context, backend_path
    ):
        CourseFactory(visibility=CourseVisibility.HIDDEN)
        result = _filter_visible_for(
            backend_path, user=AnonymousUser(), courses=Course.objects.all()
        )

        assert result.count() == 0

    def test_hidden_course_excluded_for_unregistered_authed_user(
        self, mock_site_context, backend_path
    ):
        CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()  # not registered for this course
        result = _filter_visible_for(
            backend_path, user=user, courses=Course.objects.all()
        )

        assert result.count() == 0

    def test_hidden_course_kept_for_registered_user(
        self, mock_site_context, backend_path
    ):
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        result = _filter_visible_for(
            backend_path, user=user, courses=Course.objects.all()
        )

        assert result.filter(pk=course.pk).exists()

    def test_coming_soon_course_kept_for_anonymous(
        self, mock_site_context, backend_path
    ):
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        result = _filter_visible_for(
            backend_path, user=AnonymousUser(), courses=Course.objects.all()
        )

        assert result.filter(pk=course.pk).exists()

    def test_coming_soon_course_kept_for_authenticated_user(
        self, mock_site_context, backend_path
    ):
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        result = _filter_visible_for(
            backend_path, user=UserFactory(), courses=Course.objects.all()
        )

        assert result.filter(pk=course.pk).exists()

    def test_no_duplicate_rows_when_registered_via_cohort(
        self, mock_site_context, backend_path
    ):
        """filter_visible uses Exists() not joins — no row duplication for cohort members."""
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(user=user, cohort=cohort)
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=course, is_active=True
        )
        result = list(
            _filter_visible_for(backend_path, user=user, courses=Course.objects.all())
        )

        # The hidden course is kept, and there is exactly 1 row (no duplicate)
        assert len([c for c in result if c.pk == course.pk]) == 1


@pytest.mark.django_db
class TestLoaderReturnsVisibilityEnforcingBackend:
    """get_course_access_backend() always returns a VisibilityEnforcingBackend."""

    def test_loader_returns_visibility_enforcing_backend(self, mock_site_context):
        from freedom_ls.course_access.backends import VisibilityEnforcingBackend

        backend = get_course_access_backend()
        assert isinstance(backend, VisibilityEnforcingBackend)


@pytest.mark.django_db
@pytest.mark.parametrize("backend_path", BACKEND_PATHS)
class TestVisibilityEnforcingBackendDelegatesAccessModel:
    """The wrapper delegates access-model methods to its inner backend instead of
    raising NotImplementedError.

    These methods (is_accessible_for_free, get_access_badge,
    get_dashboard_contributions) are called on the now-public catalogue/detail
    surfaces; the wrapper must pass them through to the inner backend rather than
    inherit the base class's NotImplementedError.
    """

    def test_free_course_is_accessible_for_free_delegates_true(
        self, mock_site_context, backend_path
    ):
        course = CourseFactory()  # default access_config → free
        backend = _backend_for(backend_path)

        assert backend.is_accessible_for_free(course=course) is True

    def test_free_course_badge_delegates_free_label(
        self, mock_site_context, backend_path
    ):
        course = CourseFactory()  # default access_config → free
        backend = _backend_for(backend_path)

        badge = backend.get_access_badge(course=course)

        assert badge is not None
        assert badge.label == "Free"

    def test_dashboard_contributions_empty_without_applications(
        self, mock_site_context, backend_path
    ):
        user = UserFactory()
        backend = _backend_for(backend_path)

        assert backend.get_dashboard_contributions(user=user) == []


@pytest.mark.django_db
class TestVisibilityEnforcingBackendDelegatesToApplicationBackend:
    """Delegation returns the inner backend's own answer — not a wrapper default.

    Uses the application backend, whose answers differ from the free backend's, so
    these tests would fail if the wrapper hard-coded free values instead of delegating.
    """

    application_backend = (
        "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
    )

    def test_application_gated_is_accessible_for_free_delegates_false(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        backend = _backend_for(self.application_backend)

        assert backend.is_accessible_for_free(course=course) is False

    def test_application_gated_badge_delegates_by_application_label(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        backend = _backend_for(self.application_backend)

        badge = backend.get_access_badge(course=course)

        assert badge is not None
        assert badge.label == "By application"

    def test_dashboard_contributions_delegates_application_panel(
        self, mock_site_context
    ):
        application = CourseApplicationFactory()
        backend = _backend_for(self.application_backend)

        contributions = backend.get_dashboard_contributions(user=application.user)

        assert len(contributions) == 1


@pytest.mark.django_db
class TestMinimalStubBackendEnforcement:
    """Enforcement is structural — any future backend is covered by the wrapper.

    Closes criterion 2's 'any future backend' clause mechanically.
    """

    def test_stub_backend_coming_soon_is_intercepted(self, mock_site_context):
        """Wrap a minimal stub that never handles coming_soon — wrapper still intercepts."""
        from freedom_ls.course_access.backends import (
            CourseAccessBackend,
            CourseAccessDecision,
            VisibilityEnforcingBackend,
        )

        class StubBackend(CourseAccessBackend):
            """Minimal stub — always returns a generic published decision."""

            def get_access(self, *, user, course):
                return CourseAccessDecision(
                    cta_label="Stub CTA",
                    cta_url="/stub/",
                    can_self_register=True,
                    can_access_content=True,
                )

            def filter_visible(self, *, user, courses):
                return courses

            def validate_course_config(self, raw, *, file_path=""):
                return raw

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user = UserFactory()
        wrapper = VisibilityEnforcingBackend(StubBackend())
        decision = wrapper.get_access(user=user, course=course)

        # The wrapper intercepts coming_soon; the stub's "Stub CTA" never reaches the caller.
        assert decision.can_access_content is False
        assert decision.cta_label == "I'm interested"
