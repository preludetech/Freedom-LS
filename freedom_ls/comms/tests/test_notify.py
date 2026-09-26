"""raise_notification validates in the caller and writes after commit."""

from __future__ import annotations

import pytest

from django.db import transaction

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.base.notification_categories import FLS_NOTIFICATION_CATEGORIES
from freedom_ls.comms.models import Notification
from freedom_ls.comms.notify import raise_notification
from freedom_ls.content_engine.factories import CourseFactory


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
