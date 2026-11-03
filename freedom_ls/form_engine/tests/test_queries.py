"""Tests for the form_engine query helpers that read an attempt's verdict."""

from __future__ import annotations

from typing import cast

import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)
from freedom_ls.form_engine.queries import (
    FINAL_GROUP_TITLE,
    answer_groups,
    attempt_completes_form,
    form_questions,
    quiz_verdict,
)

# A scores dict written under another strategy: populated, but with no quiz
# score to read. `qa_complete_form` used to write exactly this onto quiz forms.
NON_QUIZ_SCORES = {"Satisfaction": 5, "Recommendation": 3}


def _quiz_attempt_with_non_quiz_scores() -> FormProgress:
    """A completed QUIZ attempt holding scores that were not written by score_quiz."""
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=80)
    page = FormPageFactory(form=form, title="Quiz Page", order=0)
    FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    attempt: FormProgress = FormProgressFactory(
        user=UserFactory(),
        form=form,
        completed_time=timezone.now(),
        scores=NON_QUIZ_SCORES,
    )
    return attempt


@pytest.mark.django_db
def test_attempt_completes_form_treats_non_quiz_shaped_scores_as_complete(
    mock_site_context,
):
    """An attempt with no readable percentage has nothing to measure against the
    pass mark, so it counts as complete — the same treatment an unscored attempt
    already gets."""
    attempt = _quiz_attempt_with_non_quiz_scores()

    assert attempt_completes_form(attempt) is True


@pytest.mark.django_db
def test_quiz_verdict_returns_none_for_non_quiz_shaped_scores(mock_site_context):
    """No readable percentage means no verdict to give, rather than an exception
    escaping into the course outline."""
    attempt = _quiz_attempt_with_non_quiz_scores()

    assert quiz_verdict(attempt.form, attempt) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("strategy", "pass_percentage", "scores", "expected_verdict", "expected_complete"),
    [
        (FormStrategy.QUIZ, 80, {"score": 5, "max_score": 5}, True, True),
        (FormStrategy.QUIZ, 80, {"score": 1, "max_score": 5}, False, False),
        (FormStrategy.QUIZ, None, {"score": 1, "max_score": 5}, None, True),
        (FormStrategy.CATEGORY_VALUE_SUM, None, NON_QUIZ_SCORES, None, True),
        (FormStrategy.QUIZ, 80, NON_QUIZ_SCORES, None, True),
        (FormStrategy.QUIZ, 80, None, None, True),
    ],
    ids=[
        "a pass",
        "a fail",
        "no bar to clear",
        "a survey",
        "no percentage to read",
        "never scored",
    ],
)
def test_only_a_failed_quiz_leaves_its_form_unfinished(
    mock_site_context,
    strategy,
    pass_percentage,
    scores,
    expected_verdict,
    expected_complete,
):
    """One rule, two spellings. `quiz_verdict` answers "did they clear the bar",
    `attempt_completes_form` answers "may they move on", and the only sitting
    that stops a learner is an outright fail -- an unmarkable score is not one.

    Both answers are written out here rather than derived from each other, so a
    change that moved the two in step would still fail.
    """
    form = FormFactory(strategy=strategy, quiz_pass_percentage=pass_percentage)
    attempt: FormProgress = FormProgressFactory(
        user=UserFactory(), form=form, completed_time=timezone.now(), scores=scores
    )

    assert quiz_verdict(attempt.form, attempt) is expected_verdict
    assert attempt_completes_form(attempt) is expected_complete


@pytest.mark.django_db
def test_answer_groups_follow_page_order_and_question_order(mock_site_context):
    form = FormFactory()
    second_page = FormPageFactory(form=form, title="Second", order=1)
    first_page = FormPageFactory(form=form, title="First", order=0)
    late = FormQuestionFactory(form_page=first_page, order=5)
    early = FormQuestionFactory(form_page=first_page, order=1)
    other = FormQuestionFactory(form_page=second_page, order=0)
    progress = FormProgressFactory(form=form)
    # Created in the reverse of display order.
    QuestionAnswerFactory(form_progress=progress, question=other)
    QuestionAnswerFactory(form_progress=progress, question=late)
    QuestionAnswerFactory(form_progress=progress, question=early)

    groups = answer_groups(progress)

    assert [group.title for group in groups] == ["First", "Second"]
    assert [row.question for row in groups[0].rows] == [early, late]


@pytest.mark.django_db
def test_a_question_with_no_answer_row_gives_a_row_with_no_answer(mock_site_context):
    form = FormFactory()
    page = FormPageFactory(form=form)
    question = FormQuestionFactory(form_page=page)
    progress = FormProgressFactory(form=form)

    groups = answer_groups(progress)

    assert [(row.question, row.answer) for row in groups[0].rows] == [(question, None)]


@pytest.mark.django_db
def test_an_answer_whose_question_left_the_form_lands_in_the_final_group(
    mock_site_context,
):
    form = FormFactory()
    page = FormPageFactory(form=form)
    FormQuestionFactory(form_page=page)
    moved = FormQuestionFactory(form_page=FormPageFactory(form=FormFactory()))
    progress = FormProgressFactory(form=form)
    answer = QuestionAnswerFactory(form_progress=progress, question=moved)

    groups = answer_groups(progress)

    assert groups[-1].title == FINAL_GROUP_TITLE
    assert [(row.question, row.answer) for row in groups[-1].rows] == [(moved, answer)]
    assert len(groups) == 2


@pytest.mark.django_db
def test_a_sitting_with_every_answer_on_a_page_has_no_final_group(mock_site_context):
    form = FormFactory()
    page = FormPageFactory(form=form)
    question = FormQuestionFactory(form_page=page)
    progress = FormProgressFactory(form=form)
    QuestionAnswerFactory(form_progress=progress, question=question)

    groups = answer_groups(progress)

    assert FINAL_GROUP_TITLE not in [group.title for group in groups]


@pytest.mark.django_db
def test_answer_groups_query_count_does_not_grow_with_the_questions(
    mock_site_context, django_assert_max_num_queries
):
    def build(question_count: int) -> FormProgress:
        form = FormFactory()
        progress: FormProgress = FormProgressFactory(form=form)
        for page_order in range(2):
            page = FormPageFactory(form=form, order=page_order)
            for question_order in range(question_count):
                question = FormQuestionFactory(form_page=page, order=question_order)
                QuestionAnswerFactory(form_progress=progress, question=question)
        return progress

    small = FormProgress.objects.get(pk=build(1).pk)
    large = FormProgress.objects.get(pk=build(6).pk)

    with CaptureQueriesContext(connection) as small_queries:
        answer_groups(small)
    with django_assert_max_num_queries(len(small_queries)):
        answer_groups(large)


def _gated_form() -> tuple[Form, FormQuestion, QuestionOption, FormQuestion]:
    """A form whose second page opens only on `yes`; returns the form, the
    choice, the `yes` option and the gated page's question."""
    form: Form = FormFactory(strategy=FormStrategy.UNSCORED)
    first_page = FormPageFactory(form=form, order=0)
    choice = FormQuestionFactory(form_page=first_page, type="multiple_choice", order=0)
    yes = QuestionOptionFactory(question=choice, value="yes", order=0)
    QuestionOptionFactory(question=choice, value="no", order=1)
    gated_page = FormPageFactory(form=form, order=1, condition_option=yes)
    gated = FormQuestionFactory(form_page=gated_page, type="short_text", order=0)
    return (
        form,
        cast(FormQuestion, choice),
        cast(QuestionOption, yes),
        cast(FormQuestion, gated),
    )


def _completed_sitting_answering_no(form: Form, choice: FormQuestion) -> FormProgress:
    progress: FormProgress = FormProgressFactory(form=form)
    QuestionAnswerFactory(form_progress=progress, question=choice).selected_options.add(
        choice.options.get(value="no")
    )
    progress.complete()
    reloaded: FormProgress = FormProgress.objects.get(pk=progress.pk)
    return reloaded


def _asked_flags(progress: FormProgress) -> list[bool]:
    return [row.is_asked for group in answer_groups(progress) for row in group.rows]


@pytest.mark.django_db
def test_a_completed_sittings_off_path_question_is_not_asked_and_an_on_path_blank_is_not(
    mock_site_context,
):
    form, choice, _yes, gated = _gated_form()
    other = FormQuestionFactory(form_page=choice.form_page, type="short_text", order=1)
    progress = _completed_sitting_answering_no(form, choice)

    rows = {
        row.question.id: row for group in answer_groups(progress) for row in group.rows
    }

    assert rows[gated.id].is_asked is False
    assert rows[gated.id].answer is None
    assert rows[other.id].is_asked is True
    assert rows[other.id].answer is None


@pytest.mark.django_db
def test_an_in_progress_sittings_off_path_answer_is_not_asked_and_hides_its_value(
    mock_site_context,
):
    form, choice, _yes, gated = _gated_form()
    progress = FormProgressFactory(form=form)
    QuestionAnswerFactory(form_progress=progress, question=choice).selected_options.add(
        choice.options.get(value="no")
    )
    QuestionAnswerFactory(form_progress=progress, question=gated, text_answer="stale")

    rows = {
        row.question.id: row
        for group in answer_groups(FormProgress.objects.get(pk=progress.pk))
        for row in group.rows
    }

    assert rows[gated.id].is_asked is False
    assert rows[gated.id].answer is None


@pytest.mark.django_db
def test_a_completed_sittings_rows_ignore_later_edits_to_the_gated_pages_condition(
    mock_site_context,
):
    form, choice, _yes, gated = _gated_form()
    progress = _completed_sitting_answering_no(form, choice)
    before = _asked_flags(progress)
    gated_page = gated.form_page

    gated_page.condition_option = choice.options.get(value="no")
    gated_page.save()
    edited = _asked_flags(FormProgress.objects.get(pk=progress.pk))
    gated_page.condition_option = None
    gated_page.save()
    cleared = _asked_flags(FormProgress.objects.get(pk=progress.pk))

    assert before == [True, False]
    assert edited == before
    assert cleared == before


def _form_with_pages_prefetched(form: Form) -> Form:
    prefetched: Form = Form.objects.prefetch_related(
        "pages__text_items", "pages__questions"
    ).get(pk=form.pk)
    return prefetched


@pytest.mark.django_db
def test_form_questions_run_page_by_page_in_question_order(mock_site_context):
    form = FormFactory()
    second_page = FormPageFactory(form=form, title="Second", order=1)
    first_page = FormPageFactory(form=form, title="First", order=0)
    late = FormQuestionFactory(form_page=first_page, order=5)
    early = FormQuestionFactory(form_page=first_page, order=1)
    # A content block between two questions takes an order slot but no row.
    FormContentFactory(form_page=first_page, order=3)
    other = FormQuestionFactory(form_page=second_page, order=0)

    questions = form_questions(_form_with_pages_prefetched(form))

    assert questions == [early, late, other]


@pytest.mark.django_db
def test_form_questions_skip_a_question_on_another_forms_page(mock_site_context):
    form = FormFactory()
    mine = FormQuestionFactory(form_page=FormPageFactory(form=form, order=0))
    FormQuestionFactory(form_page=FormPageFactory(form=FormFactory(), order=0))

    questions = form_questions(_form_with_pages_prefetched(form))

    assert questions == [mine]
