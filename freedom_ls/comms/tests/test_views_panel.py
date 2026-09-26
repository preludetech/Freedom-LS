"""The bell panel fragment: the eight newest notifications, the unread
count, and marking them seen on open."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.comms.models import Notification

PANEL_URL_NAME = "comms:notification_panel"
MARK_ALL_READ_URL_NAME = "comms:notification_mark_all_read"


@pytest.mark.django_db
class TestPanelContent:
    def test_shows_only_the_eight_newest_rows(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        older = NotificationFactory.create_batch(2, user=user)
        NotificationFactory.create_batch(8, user=user)
        Notification._base_manager.filter(pk__in=[n.pk for n in older]).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        client = logged_in_client(user)

        response = client.get(reverse(PANEL_URL_NAME))

        content = response.content.decode()
        assert content.count("registered for") == 8
        assert older[0].target.title not in content
        assert older[1].target.title not in content

    def test_shows_the_unread_count(self, mock_site_context, logged_in_client) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(3, user=user)
        read = NotificationFactory(user=user)
        Notification._base_manager.filter(pk=read.pk).update(read_at=timezone.now())
        client = logged_in_client(user)

        response = client.get(reverse(PANEL_URL_NAME))

        assert "3 unread" in response.content.decode()

    def test_the_row_list_resets_the_global_list_indent(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory(user=user)
        client = logged_in_client(user)

        response = client.get(reverse(PANEL_URL_NAME))

        row_list = re.search(r'<ul class="([^"]*)"', response.content.decode())
        assert row_list is not None
        assert {"list-none", "ml-0"} <= set(row_list.group(1).split())


@pytest.mark.django_db
class TestOpeningMarksSeen:
    def test_opening_sets_seen_at_on_unseen_rows(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)

        client.get(reverse(PANEL_URL_NAME))

        notification.refresh_from_db()
        assert notification.seen_at is not None

    def test_the_response_carries_the_badge_oob_zeroed(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(3, user=user)
        client = logged_in_client(user)

        response = client.get(reverse(PANEL_URL_NAME))

        content = response.content.decode()
        assert 'hx-swap-oob="innerHTML:#notification-badge"' in content
        assert "Notifications, none new" in content


@pytest.mark.django_db
class TestPanelIsolation:
    def test_another_sites_rows_are_absent(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        other_site = SiteFactory()
        NotificationFactory(
            user=user, site=other_site, target__title="Other Site Course"
        )
        client = logged_in_client(user)

        response = client.get(reverse(PANEL_URL_NAME))

        assert "Other Site Course" not in response.content.decode()


@pytest.mark.django_db
class TestMarkAllReadFromThePanel:
    def test_returns_the_panel_fragment_and_badge_oob(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(2, user=user)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_ALL_READ_URL_NAME),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="notification-panel",
        )

        content = response.content.decode()
        assert 'id="notification-panel-heading"' in content
        assert 'hx-swap-oob="innerHTML:#notification-badge"' in content


@pytest.mark.django_db
class TestAuth:
    def test_anonymous_htmx_get_is_204_with_hx_redirect(
        self, mock_site_context
    ) -> None:
        response = Client().get(reverse(PANEL_URL_NAME), HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert "HX-Redirect" in response.headers


@pytest.mark.django_db
class TestQueryCount:
    def test_query_count_is_flat_for_2_and_200_rows(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)
        url = reverse(PANEL_URL_NAME)

        NotificationFactory.create_batch(2, user=user)
        # Warm process-level caches (ContentType, sites, the session) so
        # neither capture below pays a one-off cold-cache cost the other
        # doesn't.
        client.get(url)

        with CaptureQueriesContext(connection) as small:
            client.get(url)

        NotificationFactory.create_batch(198, user=user)
        with CaptureQueriesContext(connection) as large:
            client.get(url)

        assert len(large.captured_queries) == len(small.captured_queries)
