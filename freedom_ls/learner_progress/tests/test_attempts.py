"""Contracts of the attempt resolver in attempts.py.

Every case here is asked of a `(course_progress, collection_item)` pair, because
that is the whole point of the module: a learner holding two records for one
course must not resume one record's attempt under the other.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import cast
from unittest.mock import patch

import pytest

from django.db import DatabaseError
from django.db.models import Model
from django.utils import timezone

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.form_engine.conditions import current_path
from freedom_ls.form_engine.factories import (
    FormDeclarationFactory,
    FormFactory,
    QuestionAnswerFactory,
)
from freedom_ls.form_engine.models import (
    CompletionReason,
    Form,
    FormDeclaration,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionOption,
)
from freedom_ls.form_engine.served_paper import ensure_served_paper, served_child_ids
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_progress.attempts import (
    START_REUSE_WINDOW,
    close_left_signed_sitting,
    finalise_stale_incomplete,
    get_or_create_incomplete,
    sittings_at_placement,
    start_attempt,
)
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.tests.quiz_fixtures import ScoredQuiz, SitQuiz
from freedom_ls.tests.retire import retire


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
                cohort=cohort, course=record.course
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

    def test_a_never_opened_submit_on_exit_quiz_sitting_is_completed_with_a_served_paper(
        self, mock_site_context
    ) -> None:
        course = CourseFactory()
        record: CourseProgress = CourseProgressFactory(course=course)
        collection_item: ContentCollectionItem = ContentCollectionItemFactory(
            collection_object=course,
            child_object=FormFactory(submit_on_exit=True, strategy=FormStrategy.QUIZ),
            order=0,
        )
        open_attempt = get_or_create_incomplete(record, collection_item)

        finalise_stale_incomplete(record, collection_item)

        open_attempt.refresh_from_db()
        assert open_attempt.completed_time is not None
        assert open_attempt.served_paper is not None

    def test_an_attempt_untouched_since_the_given_instant_stays_open(
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

        result = finalise_stale_incomplete(
            record,
            collection_item,
            kept_if_untouched_since=open_attempt.last_updated_time,
        )

        assert result is None
        open_attempt.refresh_from_db()
        assert open_attempt.completed_time is None

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


@pytest.fixture
def submit_on_exit_placement(
    mock_site_context: object,
) -> tuple[CourseProgress, ContentCollectionItem]:
    course = CourseFactory()
    record: CourseProgress = CourseProgressFactory(course=course)
    collection_item: ContentCollectionItem = ContentCollectionItemFactory(
        collection_object=course,
        child_object=FormFactory(submit_on_exit=True),
        order=0,
    )
    return record, collection_item


@pytest.mark.django_db
class TestStartAttempt:
    def test_a_second_start_inside_the_window_reuses_the_open_sitting(
        self, submit_on_exit_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        """Two starts together (a double click, two tabs) used to score the first
        sitting as abandoned and open a second."""
        record, collection_item = submit_on_exit_placement
        first = start_attempt(record, collection_item)

        second = start_attempt(record, collection_item)

        assert second.pk == first.pk
        first.refresh_from_db()
        assert first.completed_time is None
        assert FormProgress.objects.count() == 1

    def test_a_start_inside_the_window_finalises_a_sitting_already_answered(
        self, submit_on_exit_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        """A learner who answered, left and pressed Start again is not a double click."""
        record, collection_item = submit_on_exit_placement
        first = start_attempt(record, collection_item)
        QuestionAnswerFactory(form_progress=first)

        second = start_attempt(record, collection_item)

        first.refresh_from_db()
        assert first.completed_time is not None
        assert second.pk != first.pk

    def test_a_start_after_the_window_finalises_the_old_sitting(
        self, submit_on_exit_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        record, collection_item = submit_on_exit_placement
        first = start_attempt(record, collection_item)
        FormProgress.objects.filter(pk=first.pk).update(
            start_time=timezone.now() - START_REUSE_WINDOW - timedelta(seconds=1)
        )

        second = start_attempt(record, collection_item)

        first.refresh_from_db()
        assert first.completed_time is not None
        assert second.pk != first.pk
        assert second.completed_time is None


def _unsaved_declaration(typed_name: str = "Thandi Nkosi") -> FormDeclaration:
    return FormDeclaration(
        declaration_text="I did this myself.",
        typed_name=typed_name,
        ip_address="203.0.113.7",
    )


@pytest.mark.django_db
class TestStartAttemptDeclaration:
    def test_a_declaration_on_a_new_record_creates_one_sitting_and_one_declaration(
        self, form_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        record, collection_item = form_placement

        sitting = start_attempt(
            record, collection_item, declaration=_unsaved_declaration()
        )

        assert FormProgress.objects.count() == 1
        declaration = FormDeclaration.objects.get()
        assert declaration.form_progress == sitting
        assert declaration.typed_name == "Thandi Nkosi"

    def test_the_declaration_shares_its_sittings_site(
        self, form_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        record, collection_item = form_placement

        sitting = start_attempt(
            record, collection_item, declaration=_unsaved_declaration()
        )

        assert FormDeclaration.objects.get().site_id == sitting.site_id

    def test_a_second_start_inside_the_window_adds_no_second_declaration(
        self, form_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        record, collection_item = form_placement
        first = start_attempt(
            record, collection_item, declaration=_unsaved_declaration("First")
        )

        second = start_attempt(
            record, collection_item, declaration=_unsaved_declaration("Second")
        )

        assert second.pk == first.pk
        assert FormDeclaration.objects.get().typed_name == "First"

    def test_a_signed_open_sitting_gets_no_second_declaration(
        self, form_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        record, collection_item = form_placement
        sitting = get_or_create_incomplete(record, collection_item)
        FormDeclarationFactory(form_progress=sitting, typed_name="Signed")
        FormProgress.objects.filter(pk=sitting.pk).update(
            start_time=timezone.now() - START_REUSE_WINDOW - timedelta(seconds=1)
        )

        start_attempt(record, collection_item, declaration=_unsaved_declaration("New"))

        assert FormDeclaration.objects.get().typed_name == "Signed"

    def test_a_declaration_signs_an_unanswered_open_sitting_instead_of_finalising_it(
        self, submit_on_exit_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        record, collection_item = submit_on_exit_placement
        sitting = get_or_create_incomplete(record, collection_item)
        FormProgress.objects.filter(pk=sitting.pk).update(
            start_time=timezone.now() - START_REUSE_WINDOW - timedelta(seconds=1)
        )

        signed = start_attempt(
            record, collection_item, declaration=_unsaved_declaration()
        )

        assert signed.pk == sitting.pk
        assert signed.completed_time is None
        assert FormDeclaration.objects.get().form_progress == signed

    def test_a_declaration_finalises_an_unsigned_answered_sitting_and_starts_a_signed_one(
        self, submit_on_exit_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        record, collection_item = submit_on_exit_placement
        old = get_or_create_incomplete(record, collection_item)
        QuestionAnswerFactory(form_progress=old)
        FormProgress.objects.filter(pk=old.pk).update(
            start_time=timezone.now() - START_REUSE_WINDOW - timedelta(seconds=1)
        )

        new = start_attempt(record, collection_item, declaration=_unsaved_declaration())

        old.refresh_from_db()
        assert old.completed_time is not None
        assert new.pk != old.pk
        assert FormDeclaration.objects.get().form_progress == new

    def test_a_start_without_a_declaration_writes_none(
        self, form_placement: tuple[CourseProgress, ContentCollectionItem]
    ) -> None:
        record, collection_item = form_placement

        start_attempt(record, collection_item)

        assert FormDeclaration.objects.exists() is False


@pytest.mark.django_db
class TestSittingsAtPlacement:
    def test_no_sitting_sets_neither_flag(self, form_placement) -> None:
        record, collection_item = form_placement

        sittings = sittings_at_placement(record, collection_item)

        assert (sittings.has_open, sittings.has_completed) == (False, False)

    def test_an_open_sitting_alone(self, form_placement) -> None:
        record, collection_item = form_placement
        CourseFormAttemptFactory(
            course_progress=record,
            collection_item=collection_item,
            form=collection_item.child,
        )

        sittings = sittings_at_placement(record, collection_item)

        assert (sittings.has_open, sittings.has_completed) == (True, False)

    def test_a_finished_sitting_alone(self, form_placement) -> None:
        record, collection_item = form_placement
        CourseFormAttemptFactory(
            course_progress=record,
            collection_item=collection_item,
            form=collection_item.child,
            form_progress__completed_time=timezone.now(),
        )

        sittings = sittings_at_placement(record, collection_item)

        assert (sittings.has_open, sittings.has_completed) == (False, True)

    def test_both_in_one_query(self, form_placement, django_assert_num_queries) -> None:
        record, collection_item = form_placement
        for completed_time in (None, timezone.now()):
            CourseFormAttemptFactory(
                course_progress=record,
                collection_item=collection_item,
                form=collection_item.child,
                form_progress__completed_time=completed_time,
            )

        with django_assert_num_queries(1):
            sittings = sittings_at_placement(record, collection_item)

        assert (sittings.has_open, sittings.has_completed) == (True, True)

    def test_another_records_sittings_do_not_count(self, form_placement) -> None:
        record, collection_item = form_placement
        other_record = CourseProgressFactory(course=record.course)
        CourseFormAttemptFactory(
            course_progress=other_record,
            collection_item=collection_item,
            form=collection_item.child,
            form_progress__completed_time=timezone.now(),
        )

        sittings = sittings_at_placement(record, collection_item)

        assert (sittings.has_open, sittings.has_completed) == (False, False)


@pytest.fixture
def scored_placement(
    course_with_scored_quiz: Callable[..., ScoredQuiz],
) -> tuple[CourseProgress, ContentCollectionItem, Form, FormQuestion, QuestionOption]:
    """A scored quiz in a course, with a learner's course progress record."""
    course, form, question, right, _wrong = course_with_scored_quiz()
    record: CourseProgress = CourseProgressFactory(course=course)
    collection_item = ContentCollectionItem.objects.get(
        collection_id=course.id, child_id=form.id
    )
    return record, collection_item, form, question, right


def _started_with_a_paper(
    record: CourseProgress, collection_item: ContentCollectionItem
) -> FormProgress:
    attempt = get_or_create_incomplete(record, collection_item)
    ensure_served_paper(attempt)
    return attempt


@pytest.mark.django_db
def test_a_sitting_started_before_a_question_retires_still_serves_and_scores_it(
    scored_placement: tuple[
        CourseProgress, ContentCollectionItem, Form, FormQuestion, QuestionOption
    ],
) -> None:
    record, collection_item, _form, question, right = scored_placement
    attempt = _started_with_a_paper(record, collection_item)
    retire(question)

    path = current_path(attempt)
    QuestionAnswerFactory(
        form_progress=attempt, question=question
    ).selected_options.add(right)
    attempt.complete()

    attempt.refresh_from_db()
    assert path.has_question(question.id)
    assert attempt.scores == {"score": 1, "max_score": 1}


@pytest.mark.django_db
def test_a_sitting_started_after_a_question_retires_is_not_served_it(
    scored_placement: tuple[
        CourseProgress, ContentCollectionItem, Form, FormQuestion, QuestionOption
    ],
) -> None:
    record, collection_item, _form, question, _right = scored_placement
    retire(question)

    attempt = _started_with_a_paper(record, collection_item)

    assert question.id not in served_child_ids(attempt.served_paper)


def _progress_snapshot() -> dict[str, list[dict[str, object]]]:
    snapshot: dict[str, list[dict[str, object]]] = {
        model.__name__: list(model._base_manager.order_by("pk").values())
        for model in (FormProgress, QuestionAnswer, CourseFormAttempt, TopicProgress)
    }
    snapshot["selected_options"] = [
        {
            "answer": answer.pk,
            "options": sorted(o.pk for o in answer.selected_options.all()),
        }
        for answer in QuestionAnswer.objects.order_by("pk")
    ]
    return snapshot


def _retire_all(*rows: Model) -> None:
    for row in rows:
        retire(row)


@pytest.mark.django_db
def test_retiring_a_topic_form_question_and_option_leaves_progress_rows_unchanged(
    scored_placement: tuple[
        CourseProgress, ContentCollectionItem, Form, FormQuestion, QuestionOption
    ],
    sit_quiz: SitQuiz,
) -> None:
    record, _collection_item, form, question, right = scored_placement
    sit_quiz(record, form, question, right)
    topic = TopicFactory()
    record.course.items.create(child=topic, order=5)
    TopicProgressFactory(course_progress=record, topic=topic)
    before = _progress_snapshot()

    _retire_all(topic, form, question, right)

    assert _progress_snapshot() == before


@pytest.fixture
def timed_save_on_exit_placement(
    mock_site_context: object,
) -> tuple[CourseProgress, ContentCollectionItem]:
    """A placement whose quiz saves on exit and has a 30 minute time limit."""
    course = CourseFactory()
    record: CourseProgress = CourseProgressFactory(course=course)
    collection_item: ContentCollectionItem = ContentCollectionItemFactory(
        collection_object=course,
        child_object=FormFactory(
            strategy=FormStrategy.QUIZ, submit_on_exit=False, time_limit_minutes=30
        ),
        order=0,
    )
    return record, collection_item


def _started_minutes_ago(sitting: FormProgress, minutes: int) -> None:
    FormProgress.objects.filter(pk=sitting.pk).update(
        start_time=timezone.now() - timedelta(minutes=minutes)
    )


@pytest.mark.django_db
class TestTimedSittings:
    def test_a_start_on_an_expired_sitting_completes_it_as_time_expired(
        self,
        timed_save_on_exit_placement: tuple[CourseProgress, ContentCollectionItem],
    ) -> None:
        record, collection_item = timed_save_on_exit_placement
        first = get_or_create_incomplete(record, collection_item)
        _started_minutes_ago(first, 31)

        second = start_attempt(record, collection_item)

        first.refresh_from_db()
        assert first.completion_reason == CompletionReason.TIME_EXPIRED
        assert second.pk != first.pk
        assert second.completed_time is None

    def test_an_expired_sitting_is_not_reused_inside_the_reuse_window(
        self,
        timed_save_on_exit_placement: tuple[CourseProgress, ContentCollectionItem],
    ) -> None:
        """A one minute limit that lapsed seconds ago is also a fresh start."""
        record, collection_item = timed_save_on_exit_placement
        Form.objects.filter(pk=cast("Form", collection_item.child).pk).update(
            time_limit_minutes=1
        )
        first = get_or_create_incomplete(record, collection_item)
        FormProgress.objects.filter(pk=first.pk).update(
            start_time=timezone.now() - timedelta(seconds=61)
        )

        second = start_attempt(record, collection_item)

        first.refresh_from_db()
        assert first.completion_reason == CompletionReason.TIME_EXPIRED
        assert second.pk != first.pk

    def test_a_course_pause_does_not_keep_an_expired_sitting_open(
        self,
        timed_save_on_exit_placement: tuple[CourseProgress, ContentCollectionItem],
    ) -> None:
        record, collection_item = timed_save_on_exit_placement
        first = get_or_create_incomplete(record, collection_item)
        _started_minutes_ago(first, 31)

        second = start_attempt(
            record,
            collection_item,
            kept_if_untouched_since=timezone.now() + timedelta(hours=1),
        )

        first.refresh_from_db()
        assert first.completion_reason == CompletionReason.TIME_EXPIRED
        assert second.pk != first.pk

    def test_an_unexpired_save_on_exit_sitting_is_still_resumed(
        self,
        timed_save_on_exit_placement: tuple[CourseProgress, ContentCollectionItem],
    ) -> None:
        record, collection_item = timed_save_on_exit_placement
        first = get_or_create_incomplete(record, collection_item)
        _started_minutes_ago(first, 5)

        second = start_attempt(record, collection_item)

        assert second.pk == first.pk
        assert second.completed_time is None

    def test_close_left_signed_sitting_completes_an_expired_sitting(
        self,
        timed_save_on_exit_placement: tuple[CourseProgress, ContentCollectionItem],
    ) -> None:
        record, collection_item = timed_save_on_exit_placement
        first = get_or_create_incomplete(record, collection_item)
        FormDeclarationFactory(form_progress=first)
        _started_minutes_ago(first, 31)

        left_open = close_left_signed_sitting(record, collection_item)

        first.refresh_from_db()
        assert left_open is None
        assert first.completion_reason == CompletionReason.TIME_EXPIRED
