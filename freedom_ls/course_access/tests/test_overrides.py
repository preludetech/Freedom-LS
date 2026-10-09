"""Tests for the shared course-access override-reading helpers."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser
from django.test import override_settings

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.backends import AccessBadge, FreeOnlyCourseAccessBackend
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_access.overrides import (
    is_coming_soon_for_display,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.tests.app_guards import app_not_installed

APPLICATION_BACKEND = (
    "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)

requires_course_applications = pytest.mark.skipif(
    app_not_installed("freedom_ls.course_applications"),
    reason="course_applications not installed",
)


@pytest.mark.django_db
class TestIsComingSoonForDisplay:
    def test_true_for_coming_soon_course_when_override_off(
        self, mock_site_context
    ) -> None:
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False):
            assert is_coming_soon_for_display(course) is True

    def test_false_for_coming_soon_course_when_override_on(
        self, mock_site_context
    ) -> None:
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
            assert is_coming_soon_for_display(course) is False

    def test_false_for_published_course(self, mock_site_context) -> None:
        course = CourseFactory(visibility=CourseVisibility.PUBLISHED)

        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False):
            assert is_coming_soon_for_display(course) is False


# Tests for OVERRIDE_COURSE_ACCESS_TO_FREE on VisibilityEnforcingBackend.
#
# Covers the wrapper forcing a free answer for a gated inner backend
# (is_accessible_for_free, get_access_badge, get_access), that the override never
# writes to Course.access_config/visibility (preview only), and that extracting the
# shared free-decision helper left FreeOnlyCourseAccessBackend.get_access unchanged.


@requires_course_applications
@pytest.mark.django_db
class TestAccessOverrideOnGatedCourse:
    def test_is_accessible_for_free_true_when_override_on(self, mock_site_context):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=True,
        ):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.is_accessible_for_free(course=course)

        assert result is True

    def test_is_accessible_for_free_false_when_override_off(self, mock_site_context):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=False,
        ):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.is_accessible_for_free(course=course)

        assert result is False

    def test_get_access_badge_reads_free_when_override_on(self, mock_site_context):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=True,
        ):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            badge = backend.get_access_badge(course=course)

        assert badge == AccessBadge(label="Free")

    def test_get_access_badge_reads_by_application_when_override_off(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=False,
        ):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            badge = backend.get_access_badge(course=course)

        assert badge == AccessBadge(label="By application")

    def test_unregistered_get_access_enrols_for_free_when_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=True,
        ):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.cta_label == "Enrol for free"
        assert decision.can_self_register is True
        assert decision.is_accessible_for_free is True

    def test_unregistered_get_access_requires_application_when_override_off(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=False,
        ):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.cta_label == "Apply now"
        assert decision.is_accessible_for_free is False

    def test_registered_learner_can_access_content_when_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=True,
        ):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(user=user, course=course)

        assert decision.cta_label == "Continue"
        assert decision.can_access_content is True


@requires_course_applications
@pytest.mark.django_db
class TestVisibilityInterceptTakesPriorityOverAccessOverride:
    """Visibility intercepts (coming_soon/hidden) still short-circuit get_access
    when only the access override is on and the visibility override is off —
    the access override must not bypass an unregistered visitor's visibility gate.
    """

    def test_hidden_course_still_closed_when_only_access_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(
            visibility=CourseVisibility.HIDDEN,
            access_config={"access_type": "application_gated"},
        )
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False,
            OVERRIDE_COURSE_ACCESS_TO_FREE=True,
        ):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.can_access_content is False
        assert decision.can_self_register is False
        assert decision.cta_label is None

    def test_coming_soon_course_still_intercepted_when_only_access_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(
            visibility=CourseVisibility.COMING_SOON,
            access_config={"access_type": "application_gated"},
        )
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False,
            OVERRIDE_COURSE_ACCESS_TO_FREE=True,
        ):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.cta_label == "I'm interested"


@requires_course_applications
@pytest.mark.django_db
class TestAccessOverrideNeverWritesDb:
    def test_course_access_config_and_visibility_unchanged_after_override(
        self, mock_site_context
    ):
        course = CourseFactory(
            access_config={"access_type": "application_gated"},
            visibility=CourseVisibility.PUBLISHED,
        )
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=True,
        ):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            backend.is_accessible_for_free(course=course)
            backend.get_access_badge(course=course)
            backend.get_access(user=UserFactory(), course=course)

        course.refresh_from_db()
        assert course.access_config == {"access_type": "application_gated"}
        assert course.visibility == CourseVisibility.PUBLISHED


@pytest.mark.django_db
class TestFreeOnlyGetAccessExtractionUnaffectedByOverride:
    """The helper extraction must not change FreeOnlyCourseAccessBackend's own
    behaviour for a genuine free course, regardless of the access override —
    the override is applied only by the wrapper, never by the inner backend.
    """

    def test_unregistered_free_course_unaffected_when_override_off(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "free"})
        with override_settings(OVERRIDE_COURSE_ACCESS_TO_FREE=False):
            decision = FreeOnlyCourseAccessBackend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.cta_label == "Enrol for free"
        assert decision.can_self_register is True
        assert decision.enrolment_summary == "Free · open"

    def test_unregistered_free_course_unaffected_when_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "free"})
        with override_settings(OVERRIDE_COURSE_ACCESS_TO_FREE=True):
            decision = FreeOnlyCourseAccessBackend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.cta_label == "Enrol for free"
        assert decision.can_self_register is True
        assert decision.enrolment_summary == "Free · open"

    def test_registered_free_course_unaffected_when_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "free"})
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
        with override_settings(OVERRIDE_COURSE_ACCESS_TO_FREE=True):
            decision = FreeOnlyCourseAccessBackend().get_access(
                user=user, course=course
            )

        assert decision.cta_label == "Continue"
        assert decision.can_access_content is True


@requires_course_applications
@pytest.mark.django_db
class TestAccessTypeOnGatedCourse:
    def test_access_type_is_free_when_override_on(self, mock_site_context):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=True,
        ):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.get_access_type(course=course)

        assert result == "free"

    def test_access_type_is_the_inner_backends_when_override_off(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "application_gated"})
        with override_settings(
            COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
            OVERRIDE_COURSE_ACCESS_TO_FREE=False,
        ):
            get_course_access_backend.cache_clear()
            backend = get_course_access_backend()
            result = backend.get_access_type(course=course)

        assert result == "application_gated"


# Tests for OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE at the VisibilityEnforcingBackend
# reachability seams (get_access, filter_visible).
#
# Covers the wrapper's coming_soon/hidden intercepts folding in the override, and
# that the override never writes to Course.visibility (preview only).


@pytest.mark.django_db
class TestGetAccessVisibilityOverride:
    def test_coming_soon_get_access_delegates_to_inner_when_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(
            visibility=CourseVisibility.COMING_SOON,
            access_config={"access_type": "free"},
        )
        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(
                user=UserFactory(), course=course
            )

        # The inner (free) backend's own decision, not the coming-soon intercept.
        assert decision.cta_label == "Enrol for free"
        assert decision.can_self_register is True

    def test_coming_soon_get_access_intercepted_when_override_off(
        self, mock_site_context
    ):
        course = CourseFactory(
            visibility=CourseVisibility.COMING_SOON,
            access_config={"access_type": "free"},
        )
        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.cta_label == "I'm interested"

    def test_hidden_get_access_delegates_to_inner_when_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(
            visibility=CourseVisibility.HIDDEN,
            access_config={"access_type": "free"},
        )
        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.cta_label == "Enrol for free"
        assert decision.can_self_register is True

    def test_hidden_get_access_intercepted_when_override_off(self, mock_site_context):
        course = CourseFactory(
            visibility=CourseVisibility.HIDDEN,
            access_config={"access_type": "free"},
        )
        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(
                user=UserFactory(), course=course
            )

        assert decision.can_access_content is False
        assert decision.can_self_register is False


@pytest.mark.django_db
class TestFilterVisibleVisibilityOverride:
    def test_hidden_course_included_for_anonymous_when_override_on(
        self, mock_site_context
    ):
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
            get_course_access_backend.cache_clear()
            result = get_course_access_backend().filter_visible(
                user=AnonymousUser(), courses=Course.objects.all()
            )

        assert result.filter(pk=course.pk).exists()


@pytest.mark.django_db
class TestVisibilityOverrideNeverWritesDb:
    def test_course_visibility_row_unchanged_after_get_access_with_override(
        self, mock_site_context
    ):
        course = CourseFactory(
            visibility=CourseVisibility.HIDDEN,
            access_config={"access_type": "free"},
        )
        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
            get_course_access_backend.cache_clear()
            get_course_access_backend().get_access(user=UserFactory(), course=course)

        course.refresh_from_db()
        assert course.visibility == CourseVisibility.HIDDEN
        assert course.access_config == {"access_type": "free"}
