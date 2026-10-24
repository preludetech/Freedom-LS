"""raise_notification validates in the caller and writes after commit."""

from __future__ import annotations

import threading
from datetime import timedelta
from unittest.mock import patch

import pytest

from django.db import IntegrityError, connection, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.base.notification_categories import FLS_NOTIFICATION_CATEGORIES
from freedom_ls.comms.factories import (
    ConversationFactory,
    CourseFactory,
    NotificationFactory,
)
from freedom_ls.comms.models import Notification
from freedom_ls.comms.notify import mark_notifications_read, raise_notification
from freedom_ls.site_aware_models.factories import SiteFactory


@pytest.mark.django_db
class TestRaiseNotificationValidation:
    def test_an_unknown_category_raises_before_any_write(
        self, mock_site_context
    ) -> None:
        course = CourseFactory()
        user = UserFactory()

        with pytest.raises(ValueError, match=r"nonexistent\.category"):
            raise_notification(
                user=user,
                category="nonexistent.category",
                target=course,
                site_id=mock_site_context.pk,
                data={},
            )

        assert not Notification._base_manager.exists()

    def test_a_missing_data_key_raises_naming_it(self, mock_site_context) -> None:
        course = CourseFactory()
        user = UserFactory()

        with pytest.raises(ValueError, match="course_title"):
            raise_notification(
                user=user,
                category="course.registered",
                target=course,
                site_id=mock_site_context.pk,
                data={},
            )

        assert not Notification._base_manager.exists()


@pytest.mark.django_db
class TestRaiseNotificationDroppedCategory:
    def test_an_fls_category_the_project_dropped_writes_nothing(
        self, mock_site_context, settings, django_capture_on_commit_callbacks
    ) -> None:
        settings.NOTIFICATION_CATEGORIES = [
            category
            for category in FLS_NOTIFICATION_CATEGORIES
            if category.key != "course.registered"
        ]
        course = CourseFactory()
        user = UserFactory()

        with django_capture_on_commit_callbacks(execute=True):
            raise_notification(
                user=user,
                category="course.registered",
                target=course,
                site_id=mock_site_context.pk,
                data={"course_title": str(course.title)},
            )

        assert not Notification._base_manager.exists()


@pytest.mark.django_db
class TestRaiseNotificationWrite:
    def test_a_valid_call_writes_one_row_with_the_given_site_target_and_data(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        course = CourseFactory()
        user = UserFactory()

        with django_capture_on_commit_callbacks(execute=True):
            raise_notification(
                user=user,
                category="course.registered",
                target=course,
                site_id=mock_site_context.pk,
                data={"course_title": str(course.title)},
            )

        notification = Notification._base_manager.get()
        assert notification.user == user
        assert notification.site_id == mock_site_context.pk
        assert notification.target == course
        assert notification.data == {"course_title": course.title}

    def test_a_rolled_back_transaction_writes_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        course = CourseFactory()
        user = UserFactory()

        def raise_and_roll_back() -> None:
            with transaction.atomic():
                raise_notification(
                    user=user,
                    category="course.registered",
                    target=course,
                    site_id=mock_site_context.pk,
                    data={"course_title": str(course.title)},
                )
                raise ZeroDivisionError

        with (
            pytest.raises(ZeroDivisionError),
            django_capture_on_commit_callbacks(execute=True),
        ):
            raise_and_roll_back()

        assert not Notification._base_manager.exists()

    def test_it_works_with_no_request(self, django_capture_on_commit_callbacks) -> None:
        """A management command has no ambient request; site_id is explicit."""
        site = SiteFactory()
        course = CourseFactory(site=site)
        user = UserFactory(site=site)

        with django_capture_on_commit_callbacks(execute=True):
            raise_notification(
                user=user,
                category="course.registered",
                target=course,
                site_id=site.pk,
                data={"course_title": str(course.title)},
            )

        assert Notification._base_manager.filter(site_id=site.pk).exists()


# Finishing a course raises no notification: the learner is on the completion page.
@pytest.mark.django_db(transaction=True)
def test_completing_a_course_notifies_nothing(
    mock_site_context, logged_in_client
) -> None:
    user = UserFactory()
    course = CourseFactory(access_config={"access_type": "free"})
    client = logged_in_client(user)
    client.post(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    )

    response = client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    )

    assert response.context["course_progress"].completed_time is not None
    assert not Notification._base_manager.filter(
        user=user, category="course.completed"
    ).exists()


@pytest.mark.django_db
def test_self_registering_for_a_course_notifies_nothing(
    mock_site_context,
    logged_in_client,
    course_with_topic,
    django_capture_on_commit_callbacks,
) -> None:
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            reverse(
                "learner_interface:initiate_course_access",
                kwargs={"course_slug": course.slug},
            )
        )

    assert response["Location"] != reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    assert not Notification._base_manager.filter(user=user).exists()


def _raise_message_received(user, conversation, site_id, sender_name="Sam"):
    raise_notification(
        user=user,
        category="message.received",
        target=conversation,
        site_id=site_id,
        data={"sender_name": sender_name},
    )


@pytest.mark.django_db
class TestRollupNotification:
    def test_the_first_event_creates_a_row_and_enqueues_delivery(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))

        with (
            override_settings(NOTIFICATION_DELIVERY_BACKENDS=["pkg.Backend"]),
            patch("freedom_ls.comms.notify.default_task_backend") as backend,
            django_capture_on_commit_callbacks(execute=True),
        ):
            _raise_message_received(user, conversation, mock_site_context.pk)

        notification = Notification.objects.get()
        assert notification.rollup_key is not None
        assert notification.target == conversation
        assert backend.enqueue.call_count == 1

    def test_a_second_event_updates_the_unread_row_without_enqueuing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        with django_capture_on_commit_callbacks(execute=True):
            _raise_message_received(user, conversation, mock_site_context.pk, "Sam")
        first = Notification.objects.get()
        Notification.objects.filter(pk=first.pk).update(
            seen_at=timezone.now(), created_at=timezone.now() - timedelta(hours=1)
        )
        old_created_at = Notification.objects.get().created_at

        with (
            override_settings(NOTIFICATION_DELIVERY_BACKENDS=["pkg.Backend"]),
            patch("freedom_ls.comms.notify.default_task_backend") as backend,
            django_capture_on_commit_callbacks(execute=True),
        ):
            _raise_message_received(user, conversation, mock_site_context.pk, "Alex")

        notification = Notification.objects.get()
        assert notification.pk == first.pk
        assert notification.seen_at is None
        assert notification.created_at > old_created_at
        assert notification.data == {"sender_name": "Alex"}
        assert backend.enqueue.call_count == 0

    def test_after_a_read_the_next_event_creates_a_new_row_and_enqueues(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        with django_capture_on_commit_callbacks(execute=True):
            _raise_message_received(user, conversation, mock_site_context.pk)
        Notification.objects.update(read_at=timezone.now())

        with (
            override_settings(NOTIFICATION_DELIVERY_BACKENDS=["pkg.Backend"]),
            patch("freedom_ls.comms.notify.default_task_backend") as backend,
            django_capture_on_commit_callbacks(execute=True),
        ):
            _raise_message_received(user, conversation, mock_site_context.pk)

        assert Notification.objects.count() == 2
        assert Notification.objects.filter(read_at__isnull=True).count() == 1
        assert backend.enqueue.call_count == 1

    def test_the_database_allows_one_unread_row_per_user_and_conversation(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        key = f"1:{conversation.pk}"
        NotificationFactory(
            user=user,
            category="message.received",
            target=conversation,
            data={"sender_name": "Sam"},
            rollup_key=key,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            NotificationFactory(
                user=user,
                category="message.received",
                target=conversation,
                data={"sender_name": "Sam"},
                rollup_key=key,
            )

    def test_a_non_rollup_category_is_unchanged(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        course = CourseFactory()
        user = UserFactory()

        with django_capture_on_commit_callbacks(execute=True):
            for _ in range(2):
                raise_notification(
                    user=user,
                    category="course.registered",
                    target=course,
                    site_id=mock_site_context.pk,
                    data={"course_title": str(course.title)},
                )

        assert Notification.objects.count() == 2
        assert Notification.objects.filter(rollup_key__isnull=True).count() == 2

    def test_the_notification_url_is_the_thread(self, mock_site_context) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        notification = NotificationFactory(
            user=user,
            category="message.received",
            target=conversation,
            data={"sender_name": "Sam"},
        )

        assert notification.url == reverse(
            "conversations:thread", kwargs={"pk": conversation.pk}
        )
        assert notification.message == "New message from Sam"


@pytest.mark.django_db(transaction=True)
def test_concurrent_raises_leave_one_unread_row(site) -> None:
    user, other = UserFactory(site=site), UserFactory(site=site)
    conversation = ConversationFactory(between=(user, other), site=site)
    barrier = threading.Barrier(4)

    def raise_one() -> None:
        try:
            barrier.wait()
            _raise_message_received(user, conversation, site.pk)
        finally:
            connection.close()

    threads = [threading.Thread(target=raise_one) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert (
        Notification._base_manager.filter(
            user=user, site=site, read_at__isnull=True
        ).count()
        == 1
    )


@pytest.mark.django_db
class TestMarkNotificationsRead:
    def test_it_reads_only_the_targets_unread_rows_for_the_user(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        elsewhere = ConversationFactory(between=(user, UserFactory()))
        mine = NotificationFactory(
            user=user,
            category="message.received",
            target=conversation,
            data={"sender_name": "Sam"},
        )
        other_target = NotificationFactory(
            user=user,
            category="message.received",
            target=elsewhere,
            data={"sender_name": "Sam"},
        )
        others = NotificationFactory(
            user=other,
            category="message.received",
            target=conversation,
            data={"sender_name": "Sam"},
        )

        mark_notifications_read(
            user=user, target=conversation, site_id=mock_site_context.pk
        )

        for row in (mine, other_target, others):
            row.refresh_from_db()
        assert mine.read_at is not None
        assert mine.seen_at is not None
        assert other_target.read_at is None
        assert others.read_at is None
