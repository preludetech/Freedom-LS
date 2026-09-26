"""The notification badge fragment: the unseen count for polling, and the
bell's own accessible name."""

from __future__ import annotations

import pytest

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.comms.factories import NotificationFactory

BADGE_URL_NAME = "comms:notification_badge"
LIST_URL_NAME = "comms:notification_list"


@pytest.mark.django_db
class TestBadgeCount:
    def test_badge_shows_the_unseen_count(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(5, user=user)
        client = logged_in_client(user)

        response = client.get(reverse(BADGE_URL_NAME))

        assert ">5<" in response.content.decode()

    def test_badge_caps_at_99_plus(self, mock_site_context, logged_in_client) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(120, user=user)
        client = logged_in_client(user)

        response = client.get(reverse(BADGE_URL_NAME))

        assert ">99+<" in response.content.decode()

    def test_badge_is_hidden_with_none_new_label_at_zero(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)

        response = client.get(reverse(BADGE_URL_NAME))

        content = response.content.decode()
        assert "Notifications, none new" in content
        assert "hidden" in content

    def test_accessible_name_carries_the_exact_count_above_99(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(120, user=user)
        client = logged_in_client(user)

        response = client.get(reverse(BADGE_URL_NAME))

        assert "Notifications, 120 new" in response.content.decode()


@pytest.mark.django_db
class TestBadgeIsolation:
    def test_another_sites_rows_do_not_count(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        other_site = SiteFactory()
        NotificationFactory(user=user, site=other_site)
        client = logged_in_client(user)

        response = client.get(reverse(BADGE_URL_NAME))

        assert "Notifications, none new" in response.content.decode()


@pytest.mark.django_db
class TestVisitingTheCentreZeroesTheBadge:
    def test_a_full_get_of_the_centre_renders_the_badge_already_zeroed(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(3, user=user)
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        assert "Notifications, none new" in response.content.decode()

    def test_fetching_the_badge_after_visiting_the_centre_gives_zero(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(3, user=user)
        client = logged_in_client(user)
        client.get(reverse(LIST_URL_NAME))

        response = client.get(reverse(BADGE_URL_NAME))

        assert "Notifications, none new" in response.content.decode()


@pytest.mark.django_db
class TestAuth:
    def test_anonymous_htmx_get_is_204_with_hx_redirect(
        self, mock_site_context
    ) -> None:
        response = Client().get(reverse(BADGE_URL_NAME), HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert "HX-Redirect" in response.headers


@pytest.mark.django_db
class TestQueryCount:
    def test_query_count_is_flat_for_2_and_200_rows(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)
        url = reverse(BADGE_URL_NAME)

        NotificationFactory.create_batch(2, user=user)
        client.get(url)

        with CaptureQueriesContext(connection) as small:
            client.get(url)

        NotificationFactory.create_batch(198, user=user)
        with CaptureQueriesContext(connection) as large:
            client.get(url)

        assert len(large.captured_queries) == len(small.captured_queries)
