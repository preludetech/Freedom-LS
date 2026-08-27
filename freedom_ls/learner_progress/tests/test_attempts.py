"""Contracts of the attempt resolver in attempts.py.

Every case here is asked of a `(course_progress, collection_item)` pair, because
that is the whole point of the module: a learner holding two records for one
course must not resume one record's attempt under the other.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

from django.db import DatabaseError
from django.utils import timezone

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_progress.attempts import (
    finalise_stale_incomplete,
    get_or_create_incomplete,
)
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
)
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress


@pytest.fixture
def form_placement(mock_site_context):
    """A record, and the collection item placing one form in its course."""
    course = CourseFactory()
    record: CourseProgress = CourseProgressFactory(course=course)
    collection_item: ContentCollectionItem = ContentCollectionItemFactory(
        collection_object=course, child_object=FormFactory(), order=0
    )
    return record, collection_item


@pytest.mark.django_db
class TestGetOrCreateIncomplete:
    def test_a_learner_with_no_attempt_gets_a_fresh_one(self, form_placement) -> None:
        record, collection_item = form_placement

        attempt = get_or_create_incomplete(record, collection_item)

        assert attempt.user == record.learner.user
        assert attempt.form == collection_item.child
        assert attempt.completed_time is None

    def test_the_course_side_is_written_too(self, form_placement) -> None:
        """An attempt with no CourseFormAttempt counts toward no percentage."""
        record, collection_item = form_placement

        attempt = get_or_create_incomplete(record, collection_item)

        course_attempt = CourseFormAttempt.objects.get(form_progress=attempt)
        assert course_attempt.course_progress_id == record.pk
        assert course_attempt.collection_item_id == collection_item.pk

    def test_an_attempt_already_under_way_is_resumed(self, form_placement) -> None:
        record, collection_item = form_placement
        existing = CourseFormAttemptFactory(
            course_progress=record,
            collection_item=collection_item,
            form=collection_item.child,
        )

        attempt = get_or_create_incomplete(record, collection_item)

        assert attempt.pk == existing.form_progress_id
        assert FormProgress.objects.count() == 1

    def test_a_finished_attempt_is_left_alone(self, form_placement) -> None:
        """Re-sitting the form starts a new attempt rather than reopening the old."""
        record, collection_item = form_placement
        completed = CourseFormAttemptFactory(
            course_progress=record,
            collection_item=collection_item,
            form=collection_item.child,
            form_progress__completed_time=timezone.now(),
        )

        attempt = get_or_create_incomplete(record, collection_item)

        assert attempt.pk != completed.form_progress_id
        assert attempt.completed_time is None
        assert FormProgress.objects.count() == 2

    def test_the_most_recently_started_open_attempt_wins(self, form_placement) -> None:
        record, collection_item = form_placement
        older = CourseFormAttemptFactory(
            course_progress=record,
            collection_item=collection_item,
            form=collection_item.child,
        )
        FormProgress.objects.filter(pk=older.form_progress_id).update(
            start_time=timezone.now() - timedelta(seconds=10)
        )
        newer = CourseFormAttemptFactory(
            course_progress=record,
            collection_item=collection_item,
            form=collection_item.child,
        )

        attempt = get_or_create_incomplete(record, collection_item)

        assert attempt.pk == newer.form_progress_id

    def test_another_records_open_attempt_is_not_resumed(self, form_placement) -> None:
        """The isolation a (user, form) lookup cannot give: one learner, one course,
        two registrations, and an attempt that belongs to only one of them."""
        record, collection_item = form_placement
        cohort = CohortFactory(organisation=record.learner.organisation)
        CohortMembershipFactory(learner=record.learner, cohort=cohort)
        other_record: CourseProgress = CourseProgressFactory(
            learner=record.learner,
            course=record.course,
            learner_registration=None,
            cohort_registration=CohortCourseRegistrationFactory(
                cohort=cohort, collection=record.course
            ),
        )
        theirs = CourseFormAttemptFactory(
            course_progress=other_record,
            collection_item=collection_item,
            form=collection_item.child,
        )

        attempt = get_or_create_incomplete(record, collection_item)

        assert attempt.pk != theirs.form_progress_id
        assert (
            CourseFormAttempt.objects.get(form_progress=attempt).course_progress_id
            == record.pk
        )

    def test_a_failed_course_side_write_leaves_no_orphan(self, form_placement) -> None:
        """Half a pair is worse than none: the FormProgress would be unfindable,
        and every answer written against it would count toward nothing."""
        record, collection_item = form_placement

        with (
            patch.object(
                CourseFormAttempt.objects,
                "create",
                side_effect=DatabaseError("the course side failed"),
            ),
            pytest.raises(DatabaseError),
        ):
            get_or_create_incomplete(record, collection_item)

        assert not FormProgress.objects.exists()


@pytest.mark.django_db
class TestFinaliseStaleIncomplete:
    def test_an_abandoned_submit_on_exit_attempt_is_completed(
        self, mock_site_context
    ) -> None:
        course = CourseFactory()
        record: CourseProgress = CourseProgressFactory(course=course)
        collection_item: ContentCollectionItem = ContentCollectionItemFactory(
            collection_object=course,
            child_object=FormFactory(submit_on_exit=True),
            order=0,
        )
        open_attempt = get_or_create_incomplete(record, collection_item)

        result = finalise_stale_incomplete(record, collection_item)

        assert result is not None
        assert result.pk == open_attempt.pk
        open_attempt.refresh_from_db()
        assert open_attempt.completed_time is not None

    def test_a_save_on_exit_attempt_stays_open(self, form_placement) -> None:
        """Left open to be resumed later -- the default form_placement is save-on-exit."""
        record, collection_item = form_placement
        open_attempt = get_or_create_incomplete(record, collection_item)

        result = finalise_stale_incomplete(record, collection_item)

        assert result is None
        open_attempt.refresh_from_db()
        assert open_attempt.completed_time is None

    def test_there_is_nothing_to_finalise_without_an_open_attempt(
        self, mock_site_context
    ) -> None:
        course = CourseFactory()
        record: CourseProgress = CourseProgressFactory(course=course)
        collection_item: ContentCollectionItem = ContentCollectionItemFactory(
            collection_object=course,
            child_object=FormFactory(submit_on_exit=True),
            order=0,
        )

        assert finalise_stale_incomplete(record, collection_item) is None
