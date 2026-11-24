"""Tests for the form_engine query helpers that read an attempt's verdict."""

from __future__ import annotations

from typing import cast

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from django.contrib.sites.models import Site
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.conditions import answers_by_question, sitting_path
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
    served_paper_of,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)
from freedom_ls.form_engine.queries import (
    FINAL_GROUP_TITLE,
    DrawingPageCounts,
    answer_groups,
    attempt_completes_form,
    count_form_questions,
    count_sitting_questions,
    drawing_page_counts,
    form_questions,
    quiz_verdict,
    stored_score_outdated,
)
from freedom_ls.tests.retire import retire

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


def _open_quiz_sitting_of_two_questions() -> tuple[
    FormProgress, FormQuestion, FormQuestion
]:
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, order=0)
    served = FormQuestionFactory(form_page=page, type="short_text", order=0)
    unserved = FormQuestionFactory(form_page=page, type="short_text", order=1)
    progress: FormProgress = FormProgressFactory(form=form)
    return progress, cast(FormQuestion, served), cast(FormQuestion, unserved)


@pytest.mark.django_db
def test_reading_an_open_quiz_sitting_with_no_served_paper_leaves_it_null(
    mock_site_context,
):
    progress, _served, _unserved = _open_quiz_sitting_of_two_questions()

    groups = answer_groups(FormProgress.objects.get(pk=progress.pk))

    assert [row.is_asked for group in groups for row in group.rows] == [True, True]
    progress.refresh_from_db()
    assert progress.served_paper is None


@pytest.mark.django_db
def test_a_served_paper_that_omits_a_question_marks_it_not_asked(mock_site_context):
    progress, served, unserved = _open_quiz_sitting_of_two_questions()
    progress.served_paper = served_paper_of([(served.form_page, [served])])
    progress.save()

    groups = answer_groups(FormProgress.objects.get(pk=progress.pk))

    rows = {row.question.id: row for group in groups for row in group.rows}
    assert rows[served.id].is_asked is True
    assert rows[unserved.id].is_asked is False


def _drawing_form() -> Form:
    """A form with a page drawing 2 of 4 single questions, a page drawing 1 of 3
    two-question groups, and a page with no draw holding 3 questions."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    single_page = FormPageFactory(form=form, order=0, draw=2)
    for order in range(4):
        FormQuestionFactory(form_page=single_page, order=order)
    group_page = FormPageFactory(form=form, order=1, draw=1)
    for group in range(3):
        for member in range(2):
            FormQuestionFactory(
                form_page=group_page, order=group * 2 + member, group=f"case-{group}"
            )
    plain_page = FormPageFactory(form=form, order=2)
    for order in range(3):
        FormQuestionFactory(form_page=plain_page, order=order)
    return form


@pytest.mark.django_db
def test_a_sitting_counts_what_each_drawing_page_draws_and_every_question_elsewhere(
    mock_site_context: object,
) -> None:
    assert count_sitting_questions(_drawing_form()) == 2 + 2 + 3


@pytest.mark.django_db
def test_a_draw_above_the_unit_count_counts_every_unit(
    mock_site_context: object,
) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, draw=9)
    for order in range(3):
        FormQuestionFactory(form_page=page, order=order)

    assert count_sitting_questions(form) == 3


@pytest.mark.django_db
def test_a_page_with_no_draw_has_no_drawing_counts(mock_site_context: object) -> None:
    page = FormPageFactory()
    FormQuestionFactory(form_page=page)

    assert drawing_page_counts(page) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("page_order", "expected"),
    [
        (0, DrawingPageCounts(2, 4, 1, False)),
        (1, DrawingPageCounts(1, 3, 2, True)),
    ],
)
def test_a_drawing_page_reports_its_units_and_questions_per_unit(
    mock_site_context: object, page_order: int, expected: DrawingPageCounts
) -> None:
    form = _drawing_form()
    page = form.pages.get(order=page_order)

    assert drawing_page_counts(page) == expected
    assert expected.drawn_question_count == (
        expected.drawn_unit_count * expected.questions_per_unit
    )


@pytest.mark.django_db
def test_a_drawing_page_mixing_groups_and_loose_questions_uses_question_wording(
    mock_site_context: object,
) -> None:
    page = FormPageFactory(form=FormFactory(strategy=FormStrategy.QUIZ), draw=2)
    FormContentFactory(form_page=page, order=0, group="case")
    FormQuestionFactory(form_page=page, order=1, group="case")
    for order in range(2, 5):
        FormQuestionFactory(form_page=page, order=order)

    counts = drawing_page_counts(page)

    assert counts == DrawingPageCounts(2, 4, 1, False)


@pytest.mark.django_db
def test_counting_sitting_questions_stays_within_a_fixed_query_budget(
    mock_site_context: object, django_assert_max_num_queries: DjangoAssertNumQueries
) -> None:
    form = Form.objects.get(pk=_drawing_form().pk)

    with django_assert_max_num_queries(8):
        count_sitting_questions(form)


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        (
            DrawingPageCounts(2, 4, 1, False),
            "Draws 2 of 4 questions per attempt",
        ),
        (
            DrawingPageCounts(1, 1, 1, False),
            "Draws 1 of 1 question per attempt",
        ),
        (
            DrawingPageCounts(2, 3, 2, True),
            "Draws 2 of 3 groups (4 questions) per attempt",
        ),
        (
            DrawingPageCounts(1, 1, 1, True),
            "Draws 1 of 1 group (1 question) per attempt",
        ),
    ],
)
def test_a_drawing_page_summary_pluralises_questions_and_groups(
    counts: DrawingPageCounts, expected: str
) -> None:
    assert counts.summary == expected


def _sat_quiz(scores: dict[str, int]) -> tuple[FormProgress, QuestionOption]:
    """A served single-question quiz sitting answered with the right option, stored with `scores`."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    page: FormPage = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="multiple_choice", order=0
    )
    right: QuestionOption = QuestionOptionFactory(
        question=question, correct=True, order=0
    )
    other: QuestionOption = QuestionOptionFactory(
        question=question, correct=False, order=1
    )
    progress: FormProgress = FormProgressFactory(
        form=form,
        scores=scores,
        completed_time=timezone.now(),
        served_paper=served_paper_of([(page, [question])], {question: [right, other]}),
    )
    QuestionAnswerFactory(
        form_progress=progress, question=question
    ).selected_options.add(right)
    reloaded: FormProgress = FormProgress.objects.get(pk=progress.pk)
    return reloaded, right


@pytest.mark.django_db
def test_stored_score_outdated_is_false_when_the_marking_is_unchanged(
    mock_site_context: Site,
) -> None:
    progress, _right = _sat_quiz({"score": 1, "max_score": 1})

    outdated = stored_score_outdated(progress, sitting_path(progress))

    assert outdated is False


@pytest.mark.django_db
def test_stored_score_outdated_is_true_when_a_correct_option_changed_after_submission(
    mock_site_context: Site,
) -> None:
    progress, right = _sat_quiz({"score": 1, "max_score": 1})
    right.correct = False
    right.save()

    outdated = stored_score_outdated(progress, sitting_path(progress))

    assert outdated is True


@pytest.mark.django_db
def test_stored_score_outdated_is_true_when_the_changed_option_is_read_from_given_answers(
    mock_site_context: Site,
) -> None:
    progress, right = _sat_quiz({"score": 1, "max_score": 1})
    right.correct = False
    right.save()
    path = sitting_path(progress)

    outdated = stored_score_outdated(progress, path, answers_by_question(progress))

    assert outdated is True


@pytest.mark.django_db
def test_stored_score_outdated_is_true_when_a_question_was_added(
    mock_site_context: Site,
) -> None:
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    right = QuestionOptionFactory(question=question, correct=True, order=0)
    progress: FormProgress = FormProgressFactory(
        form=form, scores={"score": 1, "max_score": 1}, completed_time=timezone.now()
    )
    QuestionAnswerFactory(
        form_progress=progress, question=question
    ).selected_options.add(right)
    added = FormQuestionFactory(form_page=page, type="multiple_choice", order=1)
    QuestionOptionFactory(question=added, correct=True, order=0)

    outdated = stored_score_outdated(progress, None)

    assert outdated is True


@pytest.mark.django_db
def test_stored_score_outdated_is_false_when_a_served_item_is_missing_from_the_form(
    mock_site_context: Site,
) -> None:
    progress, _right = _sat_quiz({"score": 1, "max_score": 2})
    page = progress.form.pages.get()
    unanswered = FormQuestionFactory(form_page=page, type="multiple_choice", order=1)
    served = [*page.children()]
    progress.served_paper = served_paper_of([(page, served)])
    progress.save()
    unanswered.delete()
    progress = FormProgress.objects.get(pk=progress.pk)

    outdated = stored_score_outdated(progress, sitting_path(progress))

    assert outdated is False


@pytest.mark.django_db
def test_stored_score_outdated_is_false_for_a_non_quiz_form(
    mock_site_context: Site,
) -> None:
    form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    progress: FormProgress = FormProgressFactory(
        form=form, scores={"Satisfaction": 5}, completed_time=timezone.now()
    )

    outdated = stored_score_outdated(progress, None)

    assert outdated is False


@pytest.mark.django_db
def test_count_form_questions_skips_a_retired_question_and_a_retired_page(
    mock_site_context,
):
    form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=page, order=0)
    retire(cast("FormQuestion", FormQuestionFactory(form_page=page, order=1)))
    retired_page = retire(cast("FormPage", FormPageFactory(form=form, order=1)))
    FormQuestionFactory(form_page=retired_page, order=0)

    assert count_form_questions(form) == 1


@pytest.mark.django_db
def test_count_form_questions_issues_one_query(
    mock_site_context, django_assert_num_queries
):
    form = FormFactory()
    FormQuestionFactory(form_page=FormPageFactory(form=form))

    with django_assert_num_queries(1):
        count_form_questions(form)


@pytest.mark.django_db
def test_count_sitting_questions_skips_retired_rows_on_plain_and_drawing_pages(
    mock_site_context,
):
    form = FormFactory(strategy=FormStrategy.QUIZ)
    plain_page = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=plain_page, order=0)
    retire(cast("FormQuestion", FormQuestionFactory(form_page=plain_page, order=1)))
    drawing_page = FormPageFactory(form=form, order=1, draw=3)
    FormQuestionFactory(form_page=drawing_page, order=0)
    FormQuestionFactory(form_page=drawing_page, order=1)
    retire(cast("FormQuestion", FormQuestionFactory(form_page=drawing_page, order=2)))
    retired_page = retire(cast("FormPage", FormPageFactory(form=form, order=2)))
    FormQuestionFactory(form_page=retired_page, order=0)

    assert count_sitting_questions(Form.objects.get(pk=form.pk)) == 3
