"""The backfill command walks every course progress record in the installation,
so it reads the completed-item lookups in batches. Each batch has to produce the
same percentages a single pass would."""

from __future__ import annotations

import pytest

from django.core.management import call_command

from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress


@pytest.fixture
def one_record_per_batch(monkeypatch):
    """Shrink the batch size so a handful of records still spans several batches."""
    monkeypatch.setattr(
        "freedom_ls.learner_progress.management.commands"
        ".recalculate_progress_percentages.RECORD_BATCH_SIZE",
        1,
    )


@pytest.mark.django_db
def test_percentages_are_recalculated_across_batches(
    mock_site_context,
    one_record_per_batch,
    course_with_scored_quiz,
    sit_quiz,
):
    """Passing, failing and not sitting the quiz each land on their own percentage."""
    course, form, question, right, wrong = course_with_scored_quiz(slug="backfill")
    passed_it, failed_it, never_sat_it = (
        CourseProgressFactory(course=course) for _ in range(3)
    )

    sit_quiz(passed_it, form, question, right)
    sit_quiz(failed_it, form, question, wrong)

    # The completion signal keeps these current, so stale them deliberately —
    # a backfill that changed nothing would pass the assertions below for free.
    CourseProgress.objects.filter(course=course).update(progress_percentage=55)

    call_command("recalculate_progress_percentages")

    percentages = dict(
        CourseProgress.objects.filter(course=course).values_list(
            "pk", "progress_percentage"
        )
    )
    assert percentages[passed_it.pk] == 100
    assert percentages[failed_it.pk] == 0
    assert percentages[never_sat_it.pk] == 0


@pytest.mark.django_db
def test_two_records_for_one_learner_and_course_recalculate_independently(
    mock_site_context,
    one_record_per_batch,
    course_with_scored_quiz,
    sit_quiz,
):
    """A person studying one course through two organisations is two records,
    and the backfill has to score each on its own attempts."""
    course, form, question, right, wrong = course_with_scored_quiz(slug="two-grants")
    user = LearnerFactory().user
    passed_it = CourseProgressFactory(learner=LearnerFactory(user=user), course=course)
    failed_it = CourseProgressFactory(learner=LearnerFactory(user=user), course=course)

    sit_quiz(passed_it, form, question, right)
    sit_quiz(failed_it, form, question, wrong)

    CourseProgress.objects.filter(course=course).update(progress_percentage=55)

    call_command("recalculate_progress_percentages")

    passed_it.refresh_from_db()
    failed_it.refresh_from_db()
    assert passed_it.progress_percentage == 100
    assert failed_it.progress_percentage == 0


@pytest.mark.django_db
def test_backfill_survives_an_attempt_scored_under_another_strategy(
    mock_site_context,
    course_with_scored_quiz,
    sit_quiz,
):
    """One malformed row must not abort the whole installation-wide backfill.

    Regression: a completed QUIZ attempt whose scores dict carried no "score"
    key raised KeyError out of quiz_percentage(), past the guard in
    attempt_completes_form, and killed the command mid-batch — leaving every
    record after it unrecalculated.
    """
    course, form, question, right, _wrong = course_with_scored_quiz(slug="malformed")
    unreadable = CourseProgressFactory(course=course)
    readable = CourseProgressFactory(course=course)

    unreadable_attempt = sit_quiz(unreadable, form, question, right)
    sit_quiz(readable, form, question, right)
    FormProgress.objects.filter(pk=unreadable_attempt.pk).update(
        scores={"Satisfaction": 5, "Recommendation": 3}
    )

    CourseProgress.objects.filter(course=course).update(progress_percentage=55)

    call_command("recalculate_progress_percentages")

    percentages = dict(
        CourseProgress.objects.filter(course=course).values_list(
            "pk", "progress_percentage"
        )
    )
    # No readable percentage means no verdict to hold against the learner, so
    # the attempt still counts as finishing the item.
    assert percentages[unreadable.pk] == 100
    assert percentages[readable.pk] == 100
