from __future__ import annotations

import re
from datetime import timedelta

import pytest
from lxml import html

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.comms.factories import CourseFactory, NotificationFactory
from freedom_ls.comms.models import Notification

BADGE_URL_NAME = "comms:notification_badge"
PANEL_URL_NAME = "comms:notification_panel"
LIST_URL_NAME = "comms:notification_list"
MARK_READ_URL_NAME = "comms:notification_mark_read"
MARK_UNREAD_URL_NAME = "comms:notification_mark_unread"
MARK_ALL_READ_URL_NAME = "comms:notification_mark_all_read"


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
class TestBadgeAuth:
    def test_anonymous_htmx_get_is_204_with_hx_redirect(
        self, mock_site_context
    ) -> None:
        response = Client().get(reverse(BADGE_URL_NAME), HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert "HX-Redirect" in response.headers


@pytest.mark.django_db
class TestBadgeQueryCount:
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
class TestPanelAuth:
    def test_anonymous_htmx_get_is_204_with_hx_redirect(
        self, mock_site_context
    ) -> None:
        response = Client().get(reverse(PANEL_URL_NAME), HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert "HX-Redirect" in response.headers


@pytest.mark.django_db
class TestPanelQueryCount:
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


@pytest.mark.django_db
class TestPanelMarkAllReadIcon:
    def test_mark_all_as_read_button_carries_the_check_all_icon(
        self, mock_site_context, logged_in_client
    ) -> None:
        from lxml import html

        user = UserFactory()
        NotificationFactory(user=user)
        client = logged_in_client(user)

        response = client.get(reverse(PANEL_URL_NAME))

        tree = html.fromstring(response.content.decode())
        buttons = [
            button
            for button in tree.cssselect("button")
            if "Mark all as read" in button.text_content()
        ]
        assert len(buttons) == 1
        assert buttons[0].cssselect('svg[aria-label="check_all"]')


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
class TestListAuth:
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
class TestListQueryCount:
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


@pytest.mark.django_db
class TestCentreIcons:
    def test_all_read_banner_carries_the_success_icon(
        self, mock_site_context, logged_in_client
    ) -> None:
        from lxml import html

        user = UserFactory()
        NotificationFactory(user=user, read_at=timezone.now())
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        tree = html.fromstring(response.content.decode())
        banner = tree.cssselect("#notification-list-up-to-date")
        assert len(banner) == 1
        assert banner[0].cssselect('svg[aria-label="success"]')

    def test_mark_all_as_read_button_carries_the_check_all_icon(
        self, mock_site_context, logged_in_client
    ) -> None:
        from lxml import html

        user = UserFactory()
        NotificationFactory(user=user)
        client = logged_in_client(user)

        response = client.get(reverse(LIST_URL_NAME))

        tree = html.fromstring(response.content.decode())
        buttons = [
            button
            for button in tree.cssselect("button")
            if "Mark all as read" in button.text_content()
        ]
        assert len(buttons) == 1
        assert buttons[0].cssselect('svg[aria-label="check_all"]')


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
class TestMarkAuth:
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


def _autofocused_ids(content: str) -> list[str]:
    """The id of every element the response asks htmx to focus after the
    swap."""
    ids = []
    for tag in re.findall(r"<[a-z0-9]+\b[^>]*\bautofocus\b[^>]*>", content):
        id_match = re.search(r'\bid="([^"]+)"', tag)
        assert id_match is not None, f"autofocused element has no id: {tag}"
        ids.append(id_match.group(1))
    return ids


def _unread_rows_newest_first(user, count: int) -> list[Notification]:
    """Unread rows a minute apart, so the list order is fixed rather than
    left to the id tie-break."""
    rows = NotificationFactory.create_batch(count, user=user)
    now = timezone.now()
    for minutes_ago, row in enumerate(rows):
        Notification._base_manager.filter(pk=row.pk).update(
            created_at=now - timedelta(minutes=minutes_ago)
        )
    return rows


def _toggle_id(notification: Notification) -> str:
    return f"notification-{notification.pk}-toggle-read"


@pytest.mark.django_db
class TestFocusAfterMarking:
    def test_mark_all_from_the_panel_focuses_the_panel_heading(
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

        assert _autofocused_ids(response.content.decode()) == [
            "notification-panel-heading"
        ]

    def test_mark_all_from_the_centre_focuses_the_up_to_date_banner(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory.create_batch(2, user=user)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_ALL_READ_URL_NAME),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="notification-list",
        )

        assert _autofocused_ids(response.content.decode()) == [
            "notification-list-up-to-date"
        ]

    def test_plain_renders_of_the_centre_and_panel_focus_nothing(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        read = NotificationFactory(user=user)
        read.read_at = read.created_at
        read.save(update_fields=["read_at"])
        client = logged_in_client(user)

        centre = client.get(reverse(LIST_URL_NAME))
        panel = client.get(reverse("comms:notification_panel"))

        assert "You're up to date" in centre.content.decode()
        assert _autofocused_ids(centre.content.decode()) == []
        assert _autofocused_ids(panel.content.decode()) == []

    def test_mark_read_in_the_all_view_focuses_nothing_new(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        rows = _unread_rows_newest_first(user, 2)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": rows[0].pk}),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="notification-list",
        )

        assert _autofocused_ids(response.content.decode()) == []

    def test_removing_a_row_from_the_unread_view_focuses_the_next_row(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        _newest, middle, oldest = _unread_rows_newest_first(user, 3)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": middle.pk}) + "?filter=unread",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="notification-list",
        )

        assert _autofocused_ids(response.content.decode()) == [_toggle_id(oldest)]

    def test_removing_the_last_row_from_the_unread_view_focuses_the_new_last_row(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        _newest, middle, oldest = _unread_rows_newest_first(user, 3)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": oldest.pk}) + "?filter=unread",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="notification-list",
        )

        assert _autofocused_ids(response.content.decode()) == [_toggle_id(middle)]

    def test_removing_the_only_row_from_the_unread_view_focuses_the_empty_heading(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        (only,) = _unread_rows_newest_first(user, 1)
        client = logged_in_client(user)

        response = client.post(
            reverse(MARK_READ_URL_NAME, kwargs={"pk": only.pk}) + "?filter=unread",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="notification-list",
        )

        assert _autofocused_ids(response.content.decode()) == [
            "notification-list-empty-heading"
        ]


@pytest.mark.django_db
class TestMarkQueryCount:
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


@pytest.mark.django_db
class TestRowMarkup:
    def _row(self, logged_in_client, user):
        response = logged_in_client(user).get(reverse("comms:notification_list"))
        return html.fromstring(response.content.decode()).cssselect("li")[0]

    def test_an_unread_rows_visible_label_is_hidden_from_readers(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory(user=user)

        row = self._row(logged_in_client, user)

        label = row.xpath(".//span[normalize-space(.)='Unread']")[0]
        assert label.get("aria-hidden") == "true"

    def test_the_mark_read_button_sits_outside_the_row_link(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory(user=user)

        row = self._row(logged_in_client, user)

        assert row.cssselect("a button") == []
        assert row.cssselect("button") != []

    def test_a_notification_whose_target_is_gone_has_no_link(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        course = CourseFactory()
        NotificationFactory(
            user=user, target=course, data={"course_title": course.title}
        )
        course.delete()

        row = self._row(logged_in_client, user)

        assert row.cssselect("a") == []
        assert row.cssselect("p span")
