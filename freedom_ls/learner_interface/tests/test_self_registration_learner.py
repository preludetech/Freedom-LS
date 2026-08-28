"""Tests for initiate_course_access self-registering the learner on the
default organisation.

initiate_course_access is the chokepoint for self-service course access --
see test_course_access_integration.py for the backend-branching coverage
(gated vs free, GET vs POST). These tests cover only what changed when
self-registration started keying on Learner instead of User: the Learner it
creates, its idempotence, and reactivation of a removed learner.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_management.utils import is_registered_for_course
from freedom_ls.organisations.utils import get_default_organisation


@pytest.mark.django_db
class TestInitiateCourseAccessSelfRegistration:
    def test_self_registering_creates_a_learner_on_the_default_organisation(
        self, mock_site_context, site, logged_in_client, course_with_topic
    ):
        course = course_with_topic(access_type="free")
        user = UserFactory()
        client = logged_in_client(user)
        url = reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )

        client.post(url)

        default_organisation = get_default_organisation(site)
        learner = Learner.objects.get(user=user, organisation=default_organisation)
        assert learner.is_active is True
        assert LearnerCourseRegistration.objects.filter(
            learner=learner, course=course, is_active=True
        ).exists()

    def test_self_registering_twice_creates_one_learner_and_one_registration(
        self, mock_site_context, site, logged_in_client, course_with_topic
    ):
        course = course_with_topic(access_type="free")
        user = UserFactory()
        client = logged_in_client(user)
        url = reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )

        client.post(url)
        client.post(url)

        default_organisation = get_default_organisation(site)
        assert (
            Learner.objects.filter(user=user, organisation=default_organisation).count()
            == 1
        )
        assert (
            LearnerCourseRegistration.objects.filter(
                learner__user=user, course=course
            ).count()
            == 1
        )

    def test_self_registering_reactivates_a_removed_learner(
        self, mock_site_context, site, logged_in_client, course_with_topic
    ):
        course = course_with_topic(access_type="free")
        user = UserFactory()
        default_organisation = get_default_organisation(site)
        LearnerFactory(user=user, organisation=default_organisation, is_active=False)
        client = logged_in_client(user)
        url = reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
        assert is_registered_for_course(user, course) is False

        client.post(url)

        learner = Learner.objects.get(user=user, organisation=default_organisation)
        assert learner.is_active is True
        assert is_registered_for_course(user, course) is True

    def test_self_registering_reactivates_a_deactivated_registration(
        self, mock_site_context, site, logged_in_client, course_with_topic
    ):
        """An admin may deactivate the registration rather than the Learner.
        Re-registering has to restore access: finding the row and leaving it
        inactive dead-ends the learner, since course_home then bounces them
        straight back to the course detail page."""
        course = course_with_topic(access_type="free")
        user = UserFactory()
        learner = LearnerFactory(user=user, organisation=get_default_organisation(site))
        LearnerCourseRegistrationFactory(
            learner=learner, course=course, is_active=False
        )
        client = logged_in_client(user)
        assert is_registered_for_course(user, course) is False

        client.post(
            reverse(
                "learner_interface:initiate_course_access",
                kwargs={"course_slug": course.slug},
            )
        )

        assert is_registered_for_course(user, course) is True
