"""The notification_bell inclusion tag: the poll interval it carries to the
client, and that every signed-in page shows the bell."""

from __future__ import annotations

import pytest

from django.test import override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

BELL_MARKER = 'aria-labelledby="notification-bell-label"'


@pytest.mark.django_db
class TestBellPartial:
    def test_carries_the_poll_seconds_from_an_overridden_setting(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)

        with override_settings(NOTIFICATION_BADGE_POLL_SECONDS=7):
            response = client.get(reverse("comms:notification_list"))

        assert 'data-poll-seconds="7"' in response.content.decode()


@pytest.mark.django_db
class TestBellOnEverySignedInPage:
    def test_the_dashboard_shows_the_bell(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)

        response = client.get(reverse("learner_interface:dashboard"))

        assert BELL_MARKER in response.content.decode()

    def test_the_course_player_shows_the_bell(
        self, mock_site_context, logged_in_client
    ) -> None:
        course = CourseFactory()
        topic = TopicFactory()
        course.items.create(child=topic, order=0)
        user = UserFactory()
        LearnerCourseRegistrationFactory(learner__user=user, course=course)
        client = logged_in_client(user)

        response = client.get(
            reverse(
                "learner_interface:view_course_item",
                kwargs={"course_slug": course.slug, "index": 1},
            )
        )

        assert BELL_MARKER in response.content.decode()

    def test_the_educator_interface_shows_the_bell(
        self, mock_site_context, logged_in_client
    ) -> None:
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_staff")
        client = logged_in_client(user)

        response = client.get(
            reverse(
                "educator_interface:interface",
                kwargs={
                    "organisation_slug": organisation.slug,
                    "path_string": "cohorts",
                },
            )
        )

        assert BELL_MARKER in response.content.decode()


@pytest.mark.django_db
class TestBellWhenNotificationsDisabled:
    def test_the_dashboard_hides_the_bell(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.NOTIFICATIONS_ENABLED = False
        user = UserFactory()
        client = logged_in_client(user)

        response = client.get(reverse("learner_interface:dashboard"))

        assert BELL_MARKER not in response.content.decode()
