"""The notification centre: a signed-in user's own notifications for the
current site, day-grouped and paginated, plus following one through
notification_open."""

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
from freedom_ls.content_engine.factories import CourseFactory

LIST_URL_NAME = "comms:notification_list"


@pytest.mark.django_db
class TestNotificationListIsolation:
    def test_only_the_current_users_rows_appear(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        other_user = UserFactory()
        NotificationFactory(user=user, target__title="Mine")
        NotificationFactory(user=other_user, target__title="Theirs")
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        content = response.content.decode()
        assert "Mine" in content
        assert "Theirs" not in content

    def test_only_the_current_sites_rows_appear(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        other_site = SiteFactory()
        other_course = CourseFactory(site=other_site, title="Other Site Course")
        NotificationFactory(
            user=user,
            site=other_site,
            target=other_course,
            data={"course_title": other_course.title},
        )
        own_course = CourseFactory(title="My Site Course")
        NotificationFactory(
            user=user, target=own_course, data={"course_title": own_course.title}
        )
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        content = response.content.decode()
        assert "My Site Course" in content
        assert "Other Site Course" not in content


@pytest.mark.django_db
class TestSeenState:
    def test_visiting_marks_only_the_current_users_unseen_rows_seen(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        other_user = UserFactory()
        mine = NotificationFactory(user=user)
        theirs = NotificationFactory(user=other_user)
        client = logged_in_client(user)

        client.get(reverse(LIST_URL_NAME))

        mine.refresh_from_db()
        theirs.refresh_from_db()
        assert mine.seen_at is not None
        assert theirs.seen_at is None


@pytest.mark.django_db
class TestPagination:
    def test_20_per_page_with_stable_order_when_created_at_ties(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        notifications = NotificationFactory.create_batch(25, user=user)
        Notification._base_manager.filter(user=user).update(created_at=timezone.now())
        client = logged_in_client(user)

        page1 = client.get(reverse(LIST_URL_NAME))
        page2 = client.get(reverse(LIST_URL_NAME), {"page": 2})

        page1_ids = [n.pk for n in page1.context["page_obj"].object_list]
        page2_ids = [n.pk for n in page2.context["page_obj"].object_list]

        assert len(page1_ids) == 20
        assert len(page2_ids) == 5
        assert set(page1_ids).isdisjoint(page2_ids)
        assert set(page1_ids) | set(page2_ids) == {n.pk for n in notifications}

    def test_an_htmx_get_with_page_returns_the_fragment_only(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(25, user=user)
        client = logged_in_client(user)

        response = client.get(
            reverse(LIST_URL_NAME), {"page": 2}, HTTP_HX_REQUEST="true"
        )

        content = response.content.decode()
        assert "<html" not in content.lower()
        assert 'id="notification-list"' in content

    def test_an_htmx_history_restore_gets_the_full_page(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(25, user=user)
        client = logged_in_client(user)

        response = client.get(
            reverse(LIST_URL_NAME),
            {"page": 2},
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
        )

        assert "<html" in response.content.decode().lower()

    def test_filter_links_push_the_url(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory(user=user)
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        filter_links = re.findall(
            r'<a href="[^"]*"\s+hx-get="[^"]*"[^>]*>', response.content.decode()
        )
        filter_links = [link for link in filter_links if "notification-list" in link]
        assert len(filter_links) == 2
        assert all('hx-push-url="true"' in link for link in filter_links)

    def test_pagination_links_push_the_url(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(25, user=user)
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        page_two_link = re.search(
            r'<a[^>]*hx-get="[^"]*\?page=2[^"]*"[^>]*>', response.content.decode()
        )
        assert page_two_link is not None
        assert 'hx-push-url="true"' in page_two_link.group(0)

    def test_day_groups_split_correctly_across_a_page_boundary(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        today = timezone.now()
        yesterday = today - timedelta(days=1)
        today_notifications = NotificationFactory.create_batch(15, user=user)
        yesterday_notifications = NotificationFactory.create_batch(10, user=user)
        Notification._base_manager.filter(
            pk__in=[n.pk for n in today_notifications]
        ).update(created_at=today)
        Notification._base_manager.filter(
            pk__in=[n.pk for n in yesterday_notifications]
        ).update(created_at=yesterday)
        client = logged_in_client(user)

        page1 = client.get(reverse(LIST_URL_NAME))
        page2 = client.get(reverse(LIST_URL_NAME), {"page": 2})

        page1_groups = dict(page1.context["day_groups"])
        page2_groups = dict(page2.context["day_groups"])

        assert len(page1_groups["Today"]) == 15
        assert len(page1_groups["Yesterday"]) == 5
        assert len(page2_groups["Yesterday"]) == 5


@pytest.mark.django_db
class TestRowList:
    def test_the_row_list_resets_the_global_list_indent(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory(user=user)
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        row_lists = re.findall(r'<ul class="([^"]*)"', response.content.decode())
        # The header and footer menus render <ul>s too; the row list is the
        # one carrying the row dividers.
        row_list_classes = [
            set(c.split()) for c in row_lists if "divide-border" in c.split()
        ]
        assert row_list_classes
        assert all({"list-none", "ml-0"} <= c for c in row_list_classes)


@pytest.mark.django_db
class TestNotificationOpen:
    def test_opening_sets_read_at_and_seen_at_and_redirects_to_the_live_url(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        course = CourseFactory(slug="open-course")
        notification = NotificationFactory(user=user, target=course)
        client = logged_in_client(user)

        response = client.get(
            reverse("comms:notification_open", kwargs={"pk": notification.pk})
        )

        notification.refresh_from_db()
        assert notification.read_at is not None
        assert notification.seen_at is not None
        assert response.status_code == 302
        assert response.url == "/courses/open-course/"

    def test_redirects_to_the_centre_when_the_target_is_gone(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        course = CourseFactory()
        notification = NotificationFactory(user=user, target=course)
        course.delete()
        client = logged_in_client(user)

        response = client.get(
            reverse("comms:notification_open", kwargs={"pk": notification.pk})
        )

        assert response.url == reverse(LIST_URL_NAME)

    def test_another_users_notification_id_is_404_and_unchanged(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        owner = UserFactory()
        notification = NotificationFactory(user=owner)
        client = logged_in_client(user)

        response = client.get(
            reverse("comms:notification_open", kwargs={"pk": notification.pk})
        )

        notification.refresh_from_db()
        assert response.status_code == 404
        assert notification.read_at is None


@pytest.mark.django_db
class TestAuth:
    def test_anonymous_htmx_get_of_the_list_is_204_with_hx_redirect(
        self, mock_site_context
    ) -> None:
        response = Client().get(reverse(LIST_URL_NAME), HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert "HX-Redirect" in response.headers

    def test_anonymous_htmx_get_of_open_is_204_with_hx_redirect(
        self, mock_site_context
    ) -> None:
        notification = NotificationFactory()

        response = Client().get(
            reverse("comms:notification_open", kwargs={"pk": notification.pk}),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 204
        assert "HX-Redirect" in response.headers

    def test_plain_anonymous_get_of_the_list_is_302(self, mock_site_context) -> None:
        response = Client().get(reverse(LIST_URL_NAME))

        assert response.status_code == 302


@pytest.mark.django_db
class TestQueryCount:
    def test_query_count_is_flat_for_2_and_200_rows(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        client = logged_in_client(user)
        url = reverse(LIST_URL_NAME)

        NotificationFactory.create_batch(2, user=user)
        # Warm process-level caches (ContentType, sites) so neither capture
        # below pays a one-off cold-cache cost the other doesn't.
        client.get(url)

        with CaptureQueriesContext(connection) as small:
            client.get(url)

        NotificationFactory.create_batch(198, user=user)
        with CaptureQueriesContext(connection) as large:
            client.get(url)

        assert len(large.captured_queries) == len(small.captured_queries)
