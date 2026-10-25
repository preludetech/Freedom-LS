"""Tests for the shared 404 gate over hidden and out-of-audience courses."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.http import Http404
from django.test import override_settings

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_access.visibility import raise_404_if_unavailable
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.tests.helpers import AUDIENCE_CASES

IN_AUDIENCE_CASES = [name for name, (_, inside) in AUDIENCE_CASES.items() if inside]
OUTSIDE_AUDIENCE_CASES = [
    name for name, (_, inside) in AUDIENCE_CASES.items() if not inside
]


@pytest.mark.django_db
class TestRaise404IfUnavailable:
    @pytest.mark.parametrize("case", IN_AUDIENCE_CASES)
    def test_passes_for_a_user_inside_the_audience(
        self, mock_site_context: Site, case: str
    ) -> None:
        user, course = AUDIENCE_CASES[case][0]()

        raise_404_if_unavailable(user, course)

    @pytest.mark.parametrize("case", OUTSIDE_AUDIENCE_CASES)
    def test_raises_for_a_user_outside_the_audience(
        self, mock_site_context: Site, case: str
    ) -> None:
        user, course = AUDIENCE_CASES[case][0]()

        with pytest.raises(Http404):
            raise_404_if_unavailable(user, course)

    def test_hidden_course_raises_for_an_unregistered_user(
        self, mock_site_context: Site
    ) -> None:
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)

        with pytest.raises(Http404):
            raise_404_if_unavailable(UserFactory(), course)

    def test_hidden_course_passes_for_a_registered_user(
        self, mock_site_context: Site
    ) -> None:
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )

        raise_404_if_unavailable(user, course)

    def test_visibility_override_lifts_the_audience_rule(
        self, mock_site_context: Site
    ) -> None:
        user, course = AUDIENCE_CASES["learner_of_another_organisation"][0]()

        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
            raise_404_if_unavailable(user, course)
