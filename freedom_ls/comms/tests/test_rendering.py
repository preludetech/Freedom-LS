"""Notification.message/label/icon/url read the category registry and the
row's own captured data, not a live re-render of the target on every access.
"""

from __future__ import annotations

import pytest
from lxml import html

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.factories import CourseFactory


@pytest.mark.django_db
class TestNotificationRendering:
    def test_message_uses_the_stored_title_after_the_course_is_renamed(
        self, mock_site_context
    ) -> None:
        course = CourseFactory(title="Original Title")
        notification = NotificationFactory(
            target=course, data={"course_title": course.title}
        )

        course.title = "New Title"
        course.save(update_fields=["title"])

        assert notification.message == "You've been registered for Original Title"

    def test_url_follows_the_courses_new_slug(self, mock_site_context) -> None:
        course = CourseFactory(slug="old-slug")
        notification = NotificationFactory(
            target=course, data={"course_title": course.title}
        )

        course.slug = "new-slug"
        course.save(update_fields=["slug"])

        assert notification.url == "/courses/new-slug/"

    def test_url_is_none_when_the_target_has_been_deleted(
        self, mock_site_context
    ) -> None:
        course = CourseFactory()
        notification = NotificationFactory(
            target=course, data={"course_title": course.title}
        )
        course.delete()

        assert notification.url is None

    def test_label_and_icon_come_from_the_category(self, mock_site_context) -> None:
        notification = NotificationFactory(category="course.registered")

        assert notification.label == "Course registration"
        assert notification.icon == "course"


@pytest.mark.django_db
class TestUnregisteredCategoryExclusion:
    def test_a_row_whose_category_is_not_registered_is_excluded_from_the_manager(
        self, mock_site_context
    ) -> None:
        NotificationFactory(category="nonexistent.category")

        assert not Notification.objects.exists()
        assert Notification._base_manager.exists()


@pytest.mark.django_db
class TestRowMarkup:
    def _row(self, logged_in_client, user):
        response = logged_in_client(user).get(reverse("comms:notification_list"))
        return html.fromstring(response.content.decode()).cssselect("li")[0]

    def test_an_unread_row_is_tinted_and_its_visible_label_is_hidden_from_readers(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        NotificationFactory(user=user)

        row = self._row(logged_in_client, user)

        assert "bg-primary/5" in row.get("class").split()
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
