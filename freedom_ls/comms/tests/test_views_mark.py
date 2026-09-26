"""Mark read, mark unread and mark all as read: the three POST actions that
change a notification's read_at, and the HTMX fragment they hand back."""

from __future__ import annotations

import re

import pytest

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.comms.models import Notification

MARK_READ_URL_NAME = "comms:notification_mark_read"
MARK_UNREAD_URL_NAME = "comms:notification_mark_unread"
MARK_ALL_READ_URL_NAME = "comms:notification_mark_all_read"
LIST_URL_NAME = "comms:notification_list"


@pytest.mark.django_db
class TestMarkRead:
    def test_mark_read_sets_read_at_and_seen_at(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)

        client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        notification.refresh_from_db()
        assert notification.read_at is not None
        assert notification.seen_at is not None

    def test_another_users_notification_id_is_404_and_unchanged(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        owner = UserFactory()
        notification = NotificationFactory(user=owner)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        notification.refresh_from_db()
        assert response.status_code == 404
        assert notification.read_at is None


@pytest.mark.django_db
class TestMarkUnread:
    def test_mark_unread_clears_read_at_only(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)
        client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )
        notification.refresh_from_db()
        seen_at_after_read = notification.seen_at

        client.post(
            reverse(MARK_UNREAD_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        notification.refresh_from_db()
        assert notification.read_at is None
        assert notification.seen_at == seen_at_after_read

    def test_mark_unread_after_mark_read_leaves_the_badge_at_zero(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)
        client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        client.post(
            reverse(MARK_UNREAD_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        response = client.get(reverse("comms:notification_badge"))
        assert "Notifications, none new" in response.content.decode()

    def test_another_users_notification_id_is_404_and_unchanged(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        owner = UserFactory()
        notification = NotificationFactory(user=owner)
        Notification._base_manager.filter(pk=notification.pk).update(
            read_at=notification.created_at
        )
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_UNREAD_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        notification.refresh_from_db()
        assert response.status_code == 404
        assert notification.read_at is not None


@pytest.mark.django_db
class TestMarkAllRead:
    def test_mark_all_read_touches_only_this_users_unread_rows_on_this_site(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        other_user = UserFactory()
        other_site = SiteFactory()
        mine = NotificationFactory(user=user)
        theirs = NotificationFactory(user=other_user)
        mine_other_site = NotificationFactory(user=user, site=other_site)
        client = logged_in_client(user)

        client.post(reverse(MARK_ALL_READ_URL_NAME), HTTP_HX_REQUEST="true")

        mine.refresh_from_db()
        theirs.refresh_from_db()
        mine_other_site.refresh_from_db()
        assert mine.read_at is not None
        assert theirs.read_at is None
        assert mine_other_site.read_at is None


@pytest.mark.django_db
class TestHtmxFragment:
    def test_htmx_mark_returns_the_list_fragment_and_an_oob_badge(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="notification-list",
        )

        content = response.content.decode()
        assert 'id="notification-list"' in content
        assert 'hx-swap-oob="innerHTML:#notification-badge"' in content

    def test_plain_post_redirects_to_the_centre(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk})
        )

        assert response.status_code == 302
        assert response.url == reverse(LIST_URL_NAME)

    def test_get_is_not_allowed(self, mock_site_context, logged_in_client) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)

        response = client.get(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk})
        )

        assert response.status_code == 405


@pytest.mark.django_db
class TestAuth:
    @pytest.mark.parametrize(
        ("url_name", "kwargs"),
        [
            (MARK_READ_URL_NAME, {"pk": None}),
            (MARK_UNREAD_URL_NAME, {"pk": None}),
            (MARK_ALL_READ_URL_NAME, {}),
        ],
    )
    def test_anonymous_htmx_post_is_204_with_hx_redirect(
        self, mock_site_context, url_name, kwargs
    ) -> None:
        if "pk" in kwargs:
            kwargs["pk"] = NotificationFactory().pk

        response = Client().post(
            reverse(url_name, kwargs=kwargs), HTTP_HX_REQUEST="true"
        )

        assert response.status_code == 204
        assert "HX-Redirect" in response.headers


@pytest.mark.django_db
class TestFilter:
    def test_unread_filter_lists_unread_rows_only(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory(user=user, target__title="Unread One")
        read = NotificationFactory(user=user, target__title="Read One")
        client = logged_in_client(user)
        client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": read.pk}), HTTP_HX_REQUEST="true"
        )

        response = client.get(reverse(LIST_URL_NAME), {"filter": "unread"})

        content = response.content.decode()
        assert "Unread One" in content
        assert "Read One" not in content

    def test_unread_filter_with_nothing_unread_shows_the_empty_message(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)
        client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        response = client.get(reverse(LIST_URL_NAME), {"filter": "unread"})

        assert "No unread notifications." in response.content.decode()

    def test_all_read_banner_appears_when_rows_exist_and_none_is_unread(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)
        client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        response = client.get(reverse(LIST_URL_NAME))

        assert (
            "You're up to date. Everything has been read." in response.content.decode()
        )

    def test_empty_state_appears_with_no_rows(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        assert "Nothing yet." in response.content.decode()

    def test_mark_all_as_read_is_disabled_when_nothing_is_unread(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notification = NotificationFactory(user=user)
        client = logged_in_client(user)
        client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        response = client.get(reverse(LIST_URL_NAME))

        content = response.content.decode()
        assert "Mark all as read" in content
        assert "disabled" in content

    def test_mark_all_as_read_is_absent_when_the_list_is_empty(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        assert "Mark all as read" not in response.content.decode()

    def test_pagination_links_carry_the_filter(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(25, user=user)
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME), {"filter": "unread"})

        content = response.content.decode()
        assert "filter=unread" in content

    def test_mark_read_button_on_page_2_keeps_the_response_on_page_2(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notifications = NotificationFactory.create_batch(25, user=user)
        oldest = notifications[0]
        client = logged_in_client(user)

        page_two = client.get(
            reverse(LIST_URL_NAME), {"page": 2}, HTTP_HX_REQUEST="true"
        )
        row_match = re.search(
            rf'id="notification-{oldest.pk}-toggle-read"[\s\S]*?hx-post="([^"]+)"',
            page_two.content.decode(),
        )
        assert row_match is not None
        mark_url = row_match.group(1)

        response = client.post(
            mark_url, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="notification-list"
        )

        assert "Page 2 of" in response.content.decode()


@pytest.mark.django_db
class TestQueryCount:
    def test_query_count_is_flat_for_2_and_200_rows_on_the_unread_filter(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)
        url = reverse(LIST_URL_NAME)
        params = {"filter": "unread"}

        NotificationFactory.create_batch(2, user=user)
        client.get(url, params)

        with CaptureQueriesContext(connection) as small:
            client.get(url, params)

        NotificationFactory.create_batch(198, user=user)
        with CaptureQueriesContext(connection) as large:
            client.get(url, params)

        assert len(large.captured_queries) == len(small.captured_queries)

    def test_query_count_is_flat_for_2_and_200_rows_on_a_mark_read_response(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)

        small_batch = NotificationFactory.create_batch(2, user=user)
        client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": small_batch[0].pk}),
            HTTP_HX_REQUEST="true",
        )
        with CaptureQueriesContext(connection) as small:
            client.post(
                reverse(MARK_READ_URL_NAME, kwargs={"pk": small_batch[1].pk}),
                HTTP_HX_REQUEST="true",
            )

        large_batch = NotificationFactory.create_batch(198, user=user)
        with CaptureQueriesContext(connection) as large:
            client.post(
                reverse(MARK_READ_URL_NAME, kwargs={"pk": large_batch[0].pk}),
                HTTP_HX_REQUEST="true",
            )

        assert len(large.captured_queries) == len(small.captured_queries)
