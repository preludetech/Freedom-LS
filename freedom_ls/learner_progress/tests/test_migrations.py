"""Tests for the migration that backfills CourseProgress.updated_at."""

import importlib
from datetime import UTC, datetime

import pytest

from django.apps import apps as django_apps
from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.tests.helpers import cohort_record, make_move_world

migration = importlib.import_module(
    "freedom_ls.learner_progress.migrations.0003_courseprogress_updated_at"
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
