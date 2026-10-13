"""The notification_bell inclusion tag: the poll interval it carries to the
client, and that every signed-in page shows the bell."""

from __future__ import annotations

import pytest
from lxml import html

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
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
        assign_object_role(user, organisation, "organisation_admin")
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


MESSAGES_MARKER = 'aria-labelledby="messages-button-label"'


@pytest.mark.django_db
class TestMessagesButton:
    def test_it_renders_nothing_when_messaging_is_off(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = False

        response = logged_in_client(UserFactory()).get(
            reverse("learner_interface:dashboard")
        )

        assert MESSAGES_MARKER not in response.content.decode()

    def test_it_links_to_the_inbox_when_messaging_is_on(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True

        response = logged_in_client(UserFactory()).get(
            reverse("learner_interface:dashboard")
        )

        content = response.content.decode()
        assert MESSAGES_MARKER in content
        assert f'href="{reverse("conversations:inbox")}"' in content

    def test_the_link_shows_only_the_icon(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True

        response = logged_in_client(UserFactory()).get(
            reverse("learner_interface:dashboard")
        )

        link = html.fromstring(response.content).xpath(
            "//a[@aria-labelledby='messages-button-label']"
        )[0]
        assert link.text_content().strip() == ""
        assert link.xpath(".//svg")

    def test_the_badge_element_loads_lazily_and_carries_the_poll_seconds(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True
        settings.MESSAGE_INBOX_POLL_SECONDS = 7

        response = logged_in_client(UserFactory()).get(
            reverse("learner_interface:dashboard")
        )

        content = response.content.decode()
        assert 'x-data="refreshTimer"' in content
        assert 'data-poll-seconds="7"' in content
        assert f'hx-get="{reverse("conversations:unread_badge")}"' in content
        assert 'hx-trigger="load, refresh, conversationChanged from:body"' in content

    def test_a_page_render_runs_no_conversation_query(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True
        client = logged_in_client(UserFactory())

        with CaptureQueriesContext(connection) as queries:
            client.get(reverse("learner_interface:dashboard"))

        assert not [q for q in queries if "comms_conversation" in q["sql"]]
