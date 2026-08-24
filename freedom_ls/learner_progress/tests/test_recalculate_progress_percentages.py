"""The backfill command walks every learner in the installation, so it reads the
completed-item lookups in batches. Each batch has to produce the same percentages
a single pass would."""

from __future__ import annotations

import pytest

from django.core.management import call_command

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress


@pytest.fixture
def one_learner_per_batch(monkeypatch):
    """Shrink the batch size so a handful of learners still spans several batches."""
    monkeypatch.setattr(
        "freedom_ls.learner_progress.management.commands"
        ".recalculate_progress_percentages.USER_BATCH_SIZE",
        1,
    )


@pytest.mark.django_db
def test_percentages_are_recalculated_across_batches(
    mock_site_context,
    one_learner_per_batch,
    course_with_scored_quiz,
    sit_quiz,
):
    """Passing, failing and not sitting the quiz each land on their own percentage."""
    course, form, question, right, wrong = course_with_scored_quiz(slug="backfill")
    passed_it, failed_it, never_sat_it = (UserFactory() for _ in range(3))

    for user in (passed_it, failed_it, never_sat_it):
        CourseProgressFactory(user=user, course=course)
    sit_quiz(passed_it, form, question, right)
    sit_quiz(failed_it, form, question, wrong)

    # The completion signal keeps these current, so stale them deliberately —
    # a backfill that changed nothing would pass the assertions below for free.
    CourseProgress.objects.filter(course=course).update(progress_percentage=55)

    call_command("recalculate_progress_percentages")

    percentages = dict(
        CourseProgress.objects.filter(course=course).values_list(
            "user_id", "progress_percentage"
        )
    )
    assert percentages[passed_it.pk] == 100
    assert percentages[failed_it.pk] == 0
    assert percentages[never_sat_it.pk] == 0


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
    learner after it unrecalculated.
    """
    course, form, question, right, _wrong = course_with_scored_quiz(slug="malformed")
    unreadable, readable = UserFactory(), UserFactory()

    CourseProgressFactory(user=unreadable, course=course)
    CourseProgressFactory(user=readable, course=course)
    sit_quiz(unreadable, form, question, right)
    sit_quiz(readable, form, question, right)
    FormProgress.objects.filter(user=unreadable, form=form).update(
        scores={"Satisfaction": 5, "Recommendation": 3}
    )

    CourseProgress.objects.filter(course=course).update(progress_percentage=55)

    call_command("recalculate_progress_percentages")

    percentages = dict(
        CourseProgress.objects.filter(course=course).values_list(
            "user_id", "progress_percentage"
        )
    )
    # No readable percentage means no verdict to hold against the learner, so
    # the attempt still counts as finishing the item.
    assert percentages[unreadable.pk] == 100
    assert percentages[readable.pk] == 100
