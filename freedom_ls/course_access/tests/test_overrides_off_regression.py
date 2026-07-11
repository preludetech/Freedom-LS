"""Regression test: with both preview overrides off (the default), behaviour
is unchanged from before the overrides existed.

Explicitly forces both overrides False (redundant with their False defaults,
but explicit so this test keeps guarding the contract even if a default ever
changes) and re-checks the three seams the overrides touch: a hidden course's
404 for an unregistered visitor, a coming-soon course's coming-soon decision,
and a gated course's gated badge/decision.
"""

from __future__ import annotations

import pytest

from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_access.backends import AccessBadge
from freedom_ls.course_access.loader import get_course_access_backend

APPLICATION_BACKEND = (
    "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)


@pytest.mark.django_db
class TestOverridesOffRegression:
    """Both overrides False (the default) must reproduce today's behaviour."""

    @override_settings(
        OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False,
        OVERRIDE_COURSE_ACCESS_TO_FREE=False,
    )
    def test_hidden_course_still_404s_for_unregistered_visitor(
        self, mock_site_context, course_with_topic, logged_in_client
    ):
        course = course_with_topic(
            visibility=CourseVisibility.HIDDEN, slug="hidden-course"
        )
        client = logged_in_client(UserFactory())

        get_course_access_backend.cache_clear()
        response = client.get(
            reverse(
                "student_interface:course_detail",
                kwargs={"course_slug": course.slug},
            )
        )

        assert response.status_code == 404

    @override_settings(
        OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False,
        OVERRIDE_COURSE_ACCESS_TO_FREE=False,
    )
    def test_coming_soon_course_still_presents_coming_soon(self, mock_site_context):
        course = CourseFactory(
            visibility=CourseVisibility.COMING_SOON,
            access_config={"access_type": "free"},
        )

        get_course_access_backend.cache_clear()
        decision = get_course_access_backend().get_access(
            user=UserFactory(), course=course
        )

        assert decision.cta_label == "I'm interested"
        assert decision.can_self_register is False

    @pytest.mark.skipif(
        "freedom_ls.course_applications" not in settings.INSTALLED_APPS,
        reason="course_applications not installed",
    )
    @override_settings(
        COURSE_ACCESS_BACKEND=APPLICATION_BACKEND,
        OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False,
        OVERRIDE_COURSE_ACCESS_TO_FREE=False,
    )
    def test_gated_course_still_reports_gated_badge_and_decision(
        self, mock_site_context
    ):
        course = CourseFactory(access_config={"access_type": "application_gated"})

        get_course_access_backend.cache_clear()
        backend = get_course_access_backend()
        badge = backend.get_access_badge(course=course)
        decision = backend.get_access(user=UserFactory(), course=course)

        assert badge == AccessBadge(label="By application")
        assert decision.cta_label == "Apply now"
        assert decision.is_accessible_for_free is False
