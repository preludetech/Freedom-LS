"""Tests for student_management.queries helpers.

is_registered_for_course_expression is covered in test_utils.py alongside its
non-queryset sibling, is_registered_for_course. This module holds
latest_registration.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_management.models import UserCourseRegistration
from freedom_ls.student_management.queries import latest_registration


def _backdate(registration: UserCourseRegistration, when) -> UserCourseRegistration:
    """Set registered_at directly, bypassing auto_now_add's save-time override."""
    UserCourseRegistration.objects.filter(pk=registration.pk).update(registered_at=when)
    registration.refresh_from_db()
    return registration


@pytest.mark.django_db
class TestLatestRegistration:
    """A learner can hold two registrations for one course, one per
    organisation. latest_registration picks a single deterministic row."""

    def test_no_registrations_returns_none(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()

        assert latest_registration(user, course) is None

    def test_single_active_registration_is_returned(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        registration = UserCourseRegistrationFactory(
            user=user, collection=course, is_active=True
        )

        assert latest_registration(user, course) == registration

    def test_two_active_registrations_through_different_organisations_prefers_the_newer_one(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        older = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_a, is_active=True
        )
        _backdate(older, timezone.now() - timedelta(days=7))
        newer = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_b, is_active=True
        )

        assert latest_registration(user, course) == newer

    def test_active_registration_wins_over_a_more_recent_inactive_one(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        active = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_a, is_active=True
        )
        _backdate(active, timezone.now() - timedelta(days=7))
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_b, is_active=False
        )

        assert latest_registration(user, course) == active

    def test_falls_back_to_most_recent_inactive_when_none_are_active(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        older = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_a, is_active=False
        )
        _backdate(older, timezone.now() - timedelta(days=7))
        newer = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_b, is_active=False
        )

        assert latest_registration(user, course) == newer

    def test_ignores_registrations_for_a_different_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        other_course = CourseFactory()
        UserCourseRegistrationFactory(
            user=user, collection=other_course, is_active=True
        )

        assert latest_registration(user, course) is None
