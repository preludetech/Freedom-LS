"""Tests for the data migrations that backfill CourseProgress.updated_at and User.last_active."""

import importlib
from datetime import UTC, datetime

import pytest

from django.apps import apps as django_apps
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.tests.helpers import cohort_record, make_move_world

migration = importlib.import_module(
    "freedom_ls.learner_progress.migrations.0003_courseprogress_updated_at"
)

last_active_migration = importlib.import_module(
    "freedom_ls.learner_progress.migrations.0004_backfill_user_last_active"
)

SENTINEL = datetime(2000, 1, 1, tzinfo=UTC)
JAN_1 = datetime(2024, 1, 1, tzinfo=UTC)
JAN_2 = datetime(2024, 1, 2, tzinfo=UTC)
JAN_3 = datetime(2024, 1, 3, tzinfo=UTC)
JAN_4 = datetime(2024, 1, 4, tzinfo=UTC)


def _write_timestamps(record: CourseProgress, **timestamps: datetime | None) -> None:
    """Write the timestamps and park updated_at on a sentinel, past auto_now."""
    CourseProgress._base_manager.filter(pk=record.pk).update(
        updated_at=SENTINEL, **timestamps
    )


def _backfilled_updated_at(record: CourseProgress) -> datetime:
    migration.backfill_updated_at(django_apps, None)
    record.refresh_from_db()
    return record.updated_at


@pytest.mark.django_db
class TestBackfillUpdatedAt:
    def test_a_learner_registration_record_with_only_created_at_gets_created_at(
        self, mock_site_context: Site
    ) -> None:
        record = CourseProgressFactory()
        _write_timestamps(
            record,
            created_at=JAN_1,
            started_at=None,
            last_accessed_time=None,
            completed_time=None,
        )

        assert _backfilled_updated_at(record) == JAN_1

    def test_a_cohort_registration_record_gets_the_latest_of_its_timestamps(
        self, mock_site_context: Site
    ) -> None:
        world = make_move_world()
        _, record = cohort_record(world, world.source, CourseFactory(), 50)
        _write_timestamps(
            record,
            created_at=JAN_1,
            started_at=JAN_2,
            last_accessed_time=JAN_3,
            completed_time=JAN_4,
        )

        assert _backfilled_updated_at(record) == JAN_4

    def test_a_later_last_accessed_time_beats_completed_time(
        self, mock_site_context: Site
    ) -> None:
        record = CourseProgressFactory()
        _write_timestamps(
            record,
            created_at=JAN_1,
            started_at=JAN_2,
            last_accessed_time=JAN_4,
            completed_time=JAN_3,
        )

        assert _backfilled_updated_at(record) == JAN_4


def _backfilled_last_active(user: User) -> datetime | None:
    last_active_migration.backfill_last_active(django_apps, None)
    user.refresh_from_db()
    return user.last_active


def _user_with_course_activity(
    last_login: datetime | None, *activity: datetime | None
) -> User:
    """A user with the given last login and one course record per activity time,
    each in its own organisation."""
    user: User = UserFactory(last_login=last_login)
    for accessed in activity:
        record = CourseProgressFactory(learner=LearnerFactory(user=user))
        _write_timestamps(record, last_accessed_time=accessed)
    return user


@pytest.mark.django_db
class TestBackfillLastActive:
    def test_a_later_login_than_course_activity_is_used(
        self, mock_site_context: Site
    ) -> None:
        user = _user_with_course_activity(JAN_3, JAN_2)

        assert _backfilled_last_active(user) == JAN_3

    def test_later_course_activity_than_login_is_used(
        self, mock_site_context: Site
    ) -> None:
        user = _user_with_course_activity(JAN_1, JAN_4)

        assert _backfilled_last_active(user) == JAN_4

    def test_a_user_with_only_a_login_gets_the_login(
        self, mock_site_context: Site
    ) -> None:
        user = _user_with_course_activity(JAN_2)

        assert _backfilled_last_active(user) == JAN_2

    def test_a_user_with_only_course_activity_gets_it(
        self, mock_site_context: Site
    ) -> None:
        user = _user_with_course_activity(None, JAN_3)

        assert _backfilled_last_active(user) == JAN_3

    def test_a_user_with_neither_stays_null(self, mock_site_context: Site) -> None:
        user = _user_with_course_activity(None, None)

        assert _backfilled_last_active(user) is None

    def test_course_activity_in_two_organisations_takes_the_latest(
        self, mock_site_context: Site
    ) -> None:
        user = _user_with_course_activity(JAN_1, JAN_2, JAN_4)

        assert _backfilled_last_active(user) == JAN_4
