"""Tests for VisibilityEnforcingBackend and loader wrapping.

Parametrised over both FreeOnlyCourseAccessBackend and ApplicationCourseAccessBackend
to prove enforcement is structural (the wrapper, not the inner backend).
"""

from __future__ import annotations

import pytest

from django.test import override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
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


@pytest.mark.django_db
@pytest.mark.parametrize("backend_path", BACKEND_PATHS)
class TestVisibilityEnforcingBackendGetAccess:
    """VisibilityEnforcingBackend.get_access — parametrised over both inner backends."""

    def test_coming_soon_cannot_access_content(self, mock_site_context, backend_path):
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user = UserFactory()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        assert decision.can_access_content is False

    def test_coming_soon_cannot_self_register(self, mock_site_context, backend_path):
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user = UserFactory()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        assert decision.can_self_register is False

    def test_coming_soon_cta_label_is_interested(self, mock_site_context, backend_path):
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user = UserFactory()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "I'm interested"

    def test_coming_soon_cta_url_resolves_to_express_interest(
        self, mock_site_context, backend_path
    ):
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(
            slug="my-coming-course", visibility=CourseVisibility.COMING_SOON
        )
        user = UserFactory()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        expected_url = reverse(
            "course_interest:express_interest",
            kwargs={"course_slug": "my-coming-course"},
        )
        assert decision.cta_url == expected_url

    def test_coming_soon_funnel_copy_is_coming_soon(
        self, mock_site_context, backend_path
    ):
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user = UserFactory()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        assert decision.enrolment_summary == "Coming soon"
        assert decision.acquisition_heading == "Coming soon"

    def test_coming_soon_acquisition_subtext_does_not_promise_notification(
        self, mock_site_context, backend_path
    ):
        """Funnel copy must not promise email/notify/we'll let you know."""
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user = UserFactory()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        subtext = (decision.acquisition_subtext or "").lower()
        assert "email" not in subtext
        assert "notify" not in subtext
        assert "notification" not in subtext
        assert "we'll let you know" not in subtext

    def test_hidden_unregistered_is_fully_closed(self, mock_site_context, backend_path):
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()  # not registered
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        assert decision.can_access_content is False
        assert decision.can_self_register is False
        assert decision.cta_label is None
        assert decision.cta_url is None

    def test_hidden_registered_delegates_to_inner(
        self, mock_site_context, backend_path
    ):
        """A registered user on a hidden course gets content access (delegated)."""
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        assert decision.can_access_content is True

    def test_published_delegates_to_inner_start_cta(
        self, mock_site_context, backend_path
    ):
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(
            visibility=CourseVisibility.PUBLISHED,
            access_config={"access_type": "free"},
        )
        user = UserFactory()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            decision = backend.get_access(user=user, course=course)

        # Both inner backends give "Start" for a free, unregistered course
        assert decision.cta_label == "Start"
        assert decision.can_self_register is True


@pytest.mark.django_db
@pytest.mark.parametrize("backend_path", BACKEND_PATHS)
class TestVisibilityEnforcingBackendFilterVisible:
    """VisibilityEnforcingBackend.filter_visible — parametrised over both inner backends."""

    def test_hidden_course_excluded_for_anonymous(
        self, mock_site_context, backend_path
    ):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.content_engine.models import Course
        from freedom_ls.course_access.loader import get_course_access_backend

        CourseFactory(visibility=CourseVisibility.HIDDEN)
        qs = Course.objects.all()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.filter_visible(user=AnonymousUser(), courses=qs)

        assert result.count() == 0

    def test_hidden_course_excluded_for_unregistered_authed_user(
        self, mock_site_context, backend_path
    ):
        from freedom_ls.content_engine.models import Course
        from freedom_ls.course_access.loader import get_course_access_backend

        CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()  # not registered for this course
        qs = Course.objects.all()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.filter_visible(user=user, courses=qs)

        assert result.count() == 0

    def test_hidden_course_kept_for_registered_user(
        self, mock_site_context, backend_path
    ):
        from freedom_ls.content_engine.models import Course
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        qs = Course.objects.all()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.filter_visible(user=user, courses=qs)

        assert result.filter(pk=course.pk).exists()

    def test_coming_soon_course_kept_for_anonymous(
        self, mock_site_context, backend_path
    ):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.content_engine.models import Course
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        qs = Course.objects.all()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.filter_visible(user=AnonymousUser(), courses=qs)

        assert result.filter(pk=course.pk).exists()

    def test_coming_soon_course_kept_for_authenticated_user(
        self, mock_site_context, backend_path
    ):
        from freedom_ls.content_engine.models import Course
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        user = UserFactory()
        qs = Course.objects.all()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.filter_visible(user=user, courses=qs)

        assert result.filter(pk=course.pk).exists()

    def test_no_duplicate_rows_when_registered_via_cohort(
        self, mock_site_context, backend_path
    ):
        """filter_visible uses Exists() not joins — no row duplication for cohort members."""
        from freedom_ls.content_engine.models import Course
        from freedom_ls.course_access.loader import get_course_access_backend

        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(user=user, cohort=cohort)
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=course, is_active=True
        )
        qs = Course.objects.all()
        with override_settings(COURSE_ACCESS_BACKEND=backend_path):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = list(backend.filter_visible(user=user, courses=qs))

        # The hidden course is kept, and there is exactly 1 row (no duplicate)
        assert len([c for c in result if c.pk == course.pk]) == 1


@pytest.mark.django_db
class TestLoaderReturnsVisibilityEnforcingBackend:
    """get_course_access_backend() always returns a VisibilityEnforcingBackend."""

    def test_loader_returns_visibility_enforcing_backend(self, mock_site_context):
        from freedom_ls.course_access.backends import VisibilityEnforcingBackend
        from freedom_ls.course_access.loader import get_course_access_backend

        backend = get_course_access_backend()
        assert isinstance(backend, VisibilityEnforcingBackend)


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
