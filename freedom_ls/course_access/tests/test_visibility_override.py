"""Tests for OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE at the VisibilityEnforcingBackend
reachability seams (get_access, filter_visible).

Covers the wrapper's coming_soon/hidden intercepts folding in the override, and
that the override never writes to Course.visibility (preview only).
"""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser
from django.test import override_settings

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.loader import get_course_access_backend


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

    def test_hidden_course_excluded_for_anonymous_when_override_off(
        self, mock_site_context
    ):
        CourseFactory(visibility=CourseVisibility.HIDDEN)
        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False):
            get_course_access_backend.cache_clear()
            result = get_course_access_backend().filter_visible(
                user=AnonymousUser(), courses=Course.objects.all()
            )

        assert result.count() == 0


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
