"""raise_notification validates in the caller and writes after commit."""

from __future__ import annotations

import pytest

from django.db import transaction
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.base.notification_categories import FLS_NOTIFICATION_CATEGORIES
from freedom_ls.comms.factories import CourseFactory
from freedom_ls.comms.models import Notification
from freedom_ls.comms.notify import raise_notification


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
