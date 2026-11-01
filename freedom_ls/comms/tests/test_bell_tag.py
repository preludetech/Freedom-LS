"""The notification_bell inclusion tag: the poll interval it carries to the
client, and that every signed-in page shows the bell."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
from lxml import html
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.db import connection
from django.template import Context
from django.test import Client, RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging import has_conversation
from freedom_ls.comms.templatetags.comms_tags import messages_button
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.site_aware_models.models import UnknownSite
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import drop_ambient_request

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User

LoggedInClient = Callable[["User"], Client]

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

    def test_the_panel_content_loads_from_the_recent_conversations_view(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True
        user = UserFactory()
        ConversationFactory(between=(user, UserFactory()))

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        tree = html.fromstring(response.content)
        assert MESSAGES_MARKER in response.content.decode()
        panel = tree.xpath("//*[@id='messages-panel']")[0]
        assert panel.get("hx-get") == reverse("conversations:recent")
        assert panel.get("hx-trigger") == "refresh"

    def test_the_button_has_an_icon_and_no_visible_text(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True
        user = UserFactory()
        ConversationFactory(between=(user, UserFactory()))

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        button = html.fromstring(response.content).xpath(
            "//button[@aria-labelledby='messages-button-label']"
        )[0]
        assert button.text_content().strip() == ""
        assert button.xpath(".//svg")
        assert button.get("aria-controls") == "messages-panel"

    def test_the_accessible_name_reports_the_unread_count(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True
        user = UserFactory()
        client = logged_in_client(user)
        first_sender = UserFactory()
        first_conversation = ConversationFactory(between=(user, first_sender))
        page = html.fromstring(
            client.get(reverse("learner_interface:dashboard")).content
        )
        badge = page.xpath("//*[@id='messages-badge']")[0]
        assert page.xpath("//*[@id='messages-button-label']")
        assert badge.get("hx-get") == reverse("conversations:unread_badge")
        second_sender = UserFactory()
        MessageFactory(
            conversation=ConversationFactory(between=(user, second_sender)),
            sender=second_sender,
        )
        MessageFactory(conversation=first_conversation, sender=first_sender)

        fragment = html.fromstring(
            client.get(badge.get("hx-get"), HTTP_HX_REQUEST="true").content.decode()
        )

        label = fragment.xpath("//*[@id='messages-button-label']")[0]
        assert label.text_content().strip() == "Messages, 2 unread"

    def test_the_badge_element_loads_lazily_and_carries_the_poll_seconds(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True
        settings.MESSAGE_INBOX_POLL_SECONDS = 7
        user = UserFactory()
        ConversationFactory(between=(user, UserFactory()))

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        content = response.content.decode()
        assert 'x-data="refreshTimer"' in content
        assert 'data-poll-seconds="7"' in content
        assert f'hx-get="{reverse("conversations:unread_badge")}"' in content
        assert 'hx-trigger="load, refresh, conversationChanged from:body"' in content

    def test_a_page_render_runs_no_conversation_query(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = True
        user = UserFactory()
        ConversationFactory(between=(user, UserFactory()))
        client = logged_in_client(user)

        with CaptureQueriesContext(connection) as queries:
            client.get(reverse("learner_interface:dashboard"))

        # The closing quote excludes the participant table, which render reads.
        assert not [
            q
            for q in queries
            if 'comms_conversation"' in q["sql"] or "comms_message" in q["sql"]
        ]

    def test_it_runs_no_messaging_query_when_messaging_is_off(
        self,
        mock_site_context: Site,
        logged_in_client: LoggedInClient,
        settings: SettingsWrapper,
    ) -> None:
        settings.MESSAGING_ENABLED = False
        client = logged_in_client(UserFactory())

        with CaptureQueriesContext(connection) as queries:
            response = client.get(reverse("learner_interface:dashboard"))

        assert not [q for q in queries if "comms_conversation" in q["sql"]]
        assert not [q for q in queries if "sitemessagingconfig" in q["sql"]]
        assert MESSAGES_MARKER not in response.content.decode()

    def test_a_user_with_no_learner_row_and_no_conversation_sees_no_button(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        response = logged_in_client(UserFactory()).get(
            reverse("learner_interface:dashboard")
        )

        assert MESSAGES_MARKER not in response.content.decode()

    def test_a_staff_user_with_no_recipients_sees_no_button(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        response = logged_in_client(UserFactory(staff=True)).get(
            reverse("learner_interface:dashboard")
        )

        assert MESSAGES_MARKER not in response.content.decode()

    def test_a_user_with_no_recipients_but_a_conversation_sees_the_button(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        user = UserFactory()
        ConversationFactory(between=(user, UserFactory()))

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        assert MESSAGES_MARKER in response.content.decode()

    def test_a_conversation_on_another_site_does_not_show_the_button(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        user = UserFactory()
        ConversationFactory(between=(user, UserFactory()), site=SiteFactory())

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        assert MESSAGES_MARKER not in response.content.decode()

    def test_a_user_with_a_conversation_runs_none_of_the_recipients_queries(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        user = UserFactory()
        ConversationFactory(between=(user, UserFactory()))
        client = logged_in_client(user)
        client.get(reverse("learner_interface:dashboard"))

        with CaptureQueriesContext(connection) as queries:
            client.get(reverse("learner_interface:dashboard"))

        assert not [q for q in queries if "sitemessagingconfig" in q["sql"]]

    def test_a_user_without_the_button_still_gets_the_messages_page(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        response = logged_in_client(UserFactory()).get(reverse("conversations:inbox"))

        assert response.status_code == 200

    def test_the_messages_page_asks_the_policy_for_recipients_once(
        self,
        mock_site_context: Site,
        logged_in_client: LoggedInClient,
        mocker: MockerFixture,
    ) -> None:
        from freedom_ls.comms import messaging_views

        spy = mocker.spy(messaging_views, "has_recipients")

        logged_in_client(UserFactory()).get(reverse("conversations:inbox"))

        assert spy.call_count == 1


@pytest.mark.django_db
class TestMessagesButtonTag:
    def test_an_anonymous_visitor_gets_no_button_and_no_query(
        self, mock_site_context: Site
    ) -> None:
        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        with CaptureQueriesContext(connection) as queries:
            result = messages_button(Context({"request": request}))

        assert result == {"enabled": False}
        assert not queries.captured_queries

    def test_a_rejected_host_gets_no_button_and_no_query(
        self, mock_site_context: Site, mocker: MockerFixture
    ) -> None:
        mocker.patch(
            "freedom_ls.comms.templatetags.comms_tags.get_cached_site",
            return_value=UnknownSite(),
        )
        request = RequestFactory().get("/")
        request.user = UserFactory()

        with CaptureQueriesContext(connection) as queries:
            result = messages_button(Context({"request": request}))

        assert result == {"enabled": False}
        assert not queries.captured_queries


@pytest.mark.django_db
class TestHasConversation:
    def test_it_is_false_when_the_only_conversation_is_on_another_site(
        self, mock_site_context: Site
    ) -> None:
        site = mock_site_context
        user = UserFactory()
        ConversationFactory(between=(user, UserFactory()), site=SiteFactory())
        drop_ambient_request()

        assert has_conversation(user, site) is False

    def test_it_is_true_for_the_site_the_conversation_is_on(
        self, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        other_site = SiteFactory()
        ConversationFactory(between=(user, UserFactory()), site=other_site)
        drop_ambient_request()

        assert has_conversation(user, other_site) is True
