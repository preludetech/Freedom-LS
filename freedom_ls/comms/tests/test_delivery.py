"""Each path in NOTIFICATION_DELIVERY_BACKENDS gets its own task per stored
notification. The default empty list enqueues nothing.

import_string is mocked at its call site rather than resolving a real class
defined in this test module: freedom_ls is a namespace package (no top-level
__init__.py), so a class defined here would be imported twice under two
different module identities — once by pytest's own collection, once by
import_string's dotted-path resolution — and the two copies would not share
state.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from django.test import override_settings

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.comms.models import Notification
from freedom_ls.comms.notify import raise_notification
from freedom_ls.comms.tasks import deliver_notification
from freedom_ls.content_engine.factories import CourseFactory


@pytest.mark.django_db
class TestRaiseNotificationEnqueuesDelivery:
    def test_each_configured_backend_is_enqueued_once_for_the_notification(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        course = CourseFactory()
        user = UserFactory()

        with (
            override_settings(
                NOTIFICATION_DELIVERY_BACKENDS=["pkg.FirstBackend", "pkg.SecondBackend"]
            ),
            patch("freedom_ls.comms.notify.default_task_backend") as mock_task_backend,
            django_capture_on_commit_callbacks(execute=True),
        ):
            raise_notification(
                user=user,
                category="course.registered",
                target=course,
                site_id=mock_site_context.pk,
                data={"course_title": str(course.title)},
            )

        notification = Notification.objects.get()
        enqueued = [
            call.kwargs["args"] for call in mock_task_backend.enqueue.call_args_list
        ]
        assert enqueued == [
            ["pkg.FirstBackend", str(notification.pk), mock_site_context.pk],
            ["pkg.SecondBackend", str(notification.pk), mock_site_context.pk],
        ]
        assert all(
            call.args[0] is deliver_notification
            for call in mock_task_backend.enqueue.call_args_list
        )

    def test_the_default_empty_backend_list_enqueues_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        course = CourseFactory()
        user = UserFactory()

        with (
            patch("freedom_ls.comms.notify.default_task_backend") as mock_task_backend,
            django_capture_on_commit_callbacks(execute=True),
        ):
            raise_notification(
                user=user,
                category="course.registered",
                target=course,
                site_id=mock_site_context.pk,
                data={"course_title": str(course.title)},
            )

        mock_task_backend.enqueue.assert_not_called()


@pytest.mark.django_db
class TestDeliverNotificationTask:
    def test_resolves_the_backend_and_calls_deliver_once_with_the_notification(
        self, mock_site_context
    ) -> None:
        notification = NotificationFactory()
        backend_class = MagicMock(name="ConfiguredBackend")

        with patch(
            "freedom_ls.comms.tasks.import_string", return_value=backend_class
        ) as mock_import_string:
            deliver_notification.call(
                "pkg.ConfiguredBackend", str(notification.pk), mock_site_context.pk
            )

        mock_import_string.assert_called_once_with("pkg.ConfiguredBackend")
        backend_class.return_value.deliver.assert_called_once_with(notification)

    def test_a_raising_backend_does_not_affect_the_stored_notification(
        self, mock_site_context
    ) -> None:
        notification = NotificationFactory()
        backend_class = MagicMock(name="RaisingBackend")
        backend_class.return_value.deliver.side_effect = RuntimeError("delivery failed")

        with (
            patch("freedom_ls.comms.tasks.import_string", return_value=backend_class),
            pytest.raises(RuntimeError),
        ):
            deliver_notification.call(
                "pkg.RaisingBackend", str(notification.pk), mock_site_context.pk
            )

        assert Notification.objects.filter(pk=notification.pk).exists()

    def test_a_backend_raising_does_not_stop_another_backends_task(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        course = CourseFactory()
        user = UserFactory()
        raising_backend = MagicMock(name="RaisingBackend")
        raising_backend.return_value.deliver.side_effect = RuntimeError(
            "delivery failed"
        )
        healthy_backend = MagicMock(name="HealthyBackend")

        def resolve(path: str) -> MagicMock:
            return {
                "pkg.RaisingBackend": raising_backend,
                "pkg.HealthyBackend": healthy_backend,
            }[path]

        with (
            override_settings(
                NOTIFICATION_DELIVERY_BACKENDS=[
                    "pkg.RaisingBackend",
                    "pkg.HealthyBackend",
                ]
            ),
            patch("freedom_ls.comms.tasks.import_string", side_effect=resolve),
            django_capture_on_commit_callbacks(execute=True),
        ):
            raise_notification(
                user=user,
                category="course.registered",
                target=course,
                site_id=mock_site_context.pk,
                data={"course_title": str(course.title)},
            )

        notification = Notification.objects.get()
        assert notification.pk is not None
        healthy_backend.return_value.deliver.assert_called_once_with(notification)
