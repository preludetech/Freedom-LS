"""Tests for the QUIZ strategy: correct-option matching, scoring and review."""

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionOption,
)


def _multiple_choice_question(
    page: FormPage, *, question: str, order: int
) -> tuple[FormQuestion, QuestionOption, QuestionOption]:
    """A question with one correct option and one incorrect one, in that order."""
    form_question: FormQuestion = FormQuestionFactory(
        form_page=page,
        question=question,
        type="multiple_choice",
        order=order,
    )
    correct_option: QuestionOption = QuestionOptionFactory(
        question=form_question, text="right", value="1", order=0, correct=True
    )
    wrong_option: QuestionOption = QuestionOptionFactory(
        question=form_question, text="wrong", value="2", order=1, correct=False
    )
    return form_question, correct_option, wrong_option


def _answer(
    form_progress: FormProgress, question: FormQuestion, *options: QuestionOption
) -> QuestionAnswer:
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(*options)
    return answer


@pytest.mark.parametrize(
    ("select_correct", "expected_score"),
    [
        (True, 1),
        (False, 0),
    ],
    ids=["correct_answer_scores_one", "incorrect_answer_scores_zero"],
)
@pytest.mark.django_db
def test_score_quiz_single_question(mock_site_context, select_correct, expected_score):
    """Quiz scoring with a single question — score depends on which option was selected."""
    user = UserFactory()
    form = FormFactory()

    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )
    correct_option = QuestionOptionFactory(
        question=question, text="4", value="4", order=0, correct=True
    )
    wrong_option = QuestionOptionFactory(
        question=question, text="3", value="3", order=1, correct=False
    )
    QuestionOptionFactory(
        question=question, text="5", value="5", order=2, correct=False
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    _answer(form_progress, question, correct_option if select_correct else wrong_option)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == expected_score
    assert form_progress.scores["max_score"] == 1


@pytest.mark.django_db
def test_score_quiz_multiple_questions_mixed_answers(mock_site_context):
    """Two right and one wrong out of three questions scores 2 of 3."""
    form = FormFactory()
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question_1, correct_1, _wrong_1 = _multiple_choice_question(
        page, question="What is 2 + 2?", order=0
    )
    question_2, _correct_2, wrong_2 = _multiple_choice_question(
        page, question="What is 3 + 3?", order=1
    )
    question_3, correct_3, _wrong_3 = _multiple_choice_question(
        page, question="What is 4 + 4?", order=2
    )

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    _answer(form_progress, question_1, correct_1)
    _answer(form_progress, question_2, wrong_2)
    _answer(form_progress, question_3, correct_3)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 2, "max_score": 3}


@pytest.mark.django_db
def test_score_quiz_includes_unanswered_questions_in_max_score(
    mock_site_context,
):
    """A question the learner skipped still raises the score ceiling."""
    form = FormFactory()
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    answered_question, correct_option, _wrong_option = _multiple_choice_question(
        page, question="What is 2 + 2?", order=0
    )
    _multiple_choice_question(page, question="What is 3 + 3?", order=1)
    _multiple_choice_question(page, question="What is 4 + 4?", order=2)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    _answer(form_progress, answered_question, correct_option)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 1, "max_score": 3}


# Checkbox (multi-select) scoring: exact match, all-or-nothing.


@pytest.fixture
def checkbox_attempt(
    mock_site_context,
) -> tuple[FormProgress, QuestionAnswer, FormQuestion, list[QuestionOption]]:
    """An unanswered attempt at a quiz whose one question has 2 correct options of 4.

    Returns (form_progress, answer, question, options) where `options` is
    (correct_1, correct_2, wrong_1, wrong_2) -- each test only has to tick the
    combination it is about.
    """
    form = FormFactory(strategy=FormStrategy.QUIZ)
    question, *options = _build_checkbox_question_two_of_four(form)
    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    return form_progress, answer, question, options


def _build_checkbox_question_two_of_four(
    form: Form,
) -> tuple[
    FormQuestion, QuestionOption, QuestionOption, QuestionOption, QuestionOption
]:
    """Checkbox question with 2 correct options of 4, mirroring the qa_helpers fixture shape."""
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page,
        question="Select all prime numbers",
        type="checkboxes",
        order=0,
    )
    correct_option_1: QuestionOption = QuestionOptionFactory(
        question=question, text="2", value="2", order=0, correct=True
    )
    correct_option_2: QuestionOption = QuestionOptionFactory(
        question=question, text="3", value="3", order=1, correct=True
    )
    wrong_option_1: QuestionOption = QuestionOptionFactory(
        question=question, text="4", value="4", order=2, correct=False
    )
    wrong_option_2: QuestionOption = QuestionOptionFactory(
        question=question, text="6", value="6", order=3, correct=False
    )
    return question, correct_option_1, correct_option_2, wrong_option_1, wrong_option_2


@pytest.mark.django_db
def test_score_quiz_checkbox_exactly_correct_options_scores_one(checkbox_attempt):
    """Ticking exactly the 2 correct options of 4 scores full marks."""
    form_progress, answer, _question, options = checkbox_attempt
    correct_1, correct_2, _wrong_1, _wrong_2 = options
    answer.selected_options.add(correct_1, correct_2)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 1
    assert form_progress.scores["max_score"] == 1
    assert form_progress.get_incorrect_quiz_answers() == []


@pytest.mark.django_db
def test_score_quiz_checkbox_ticking_all_four_scores_zero(checkbox_attempt):
    """The headline bug: ticking every option (2 correct, 2 incorrect) must not score full marks."""
    form_progress, answer, question, options = checkbox_attempt
    correct_1, correct_2, wrong_1, wrong_2 = options
    answer.selected_options.add(correct_1, correct_2, wrong_1, wrong_2)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


@pytest.mark.django_db
def test_score_quiz_checkbox_partial_correct_selection_scores_zero(checkbox_attempt):
    """Ticking only 1 of the 2 correct options scores zero — no partial credit."""
    form_progress, answer, question, options = checkbox_attempt
    correct_1, _correct_2, _wrong_1, _wrong_2 = options
    answer.selected_options.add(correct_1)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


@pytest.mark.django_db
def test_score_quiz_checkbox_correct_plus_incorrect_scores_zero(checkbox_attempt):
    """Ticking both correct options plus one incorrect option scores zero."""
    form_progress, answer, question, options = checkbox_attempt
    correct_1, correct_2, wrong_1, _wrong_2 = options
    answer.selected_options.add(correct_1, correct_2, wrong_1)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


@pytest.mark.django_db
def test_score_quiz_checkbox_nothing_selected_scores_zero(checkbox_attempt):
    """A QuestionAnswer exists but has no selected options — scores zero."""
    form_progress, _answer, question, _options = checkbox_attempt

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


# A question left blank stores no QuestionAnswer row at all. It still counts
# toward max_score, so the review list has to account for it too — otherwise a
# learner is failed over a question the page never names.


@pytest.mark.django_db
def test_get_incorrect_quiz_answers_lists_a_question_with_no_answer_row(
    mock_site_context,
):
    """A question left blank is listed as incorrect, with nothing recorded as selected."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    question, _correct_1, _correct_2, _wrong_1, _wrong_2 = (
        _build_checkbox_question_two_of_four(form)
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)

    incorrect = form_progress.get_incorrect_quiz_answers()

    assert [item["question"] for item in incorrect] == [question]
    assert incorrect[0]["learner_selected"] == []


@pytest.mark.django_db
def test_get_incorrect_quiz_answers_agrees_with_score_quiz_on_a_blank_question(
    mock_site_context,
):
    """One question answered right, one left blank: the score says 1 of 2 and the list names
    the blank one alone."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    answered_question, correct_1, correct_2, _wrong_1, _wrong_2 = (
        _build_checkbox_question_two_of_four(form)
    )
    blank_page = FormPageFactory(form=form, title="Quiz Page 2", order=1)
    blank_question = FormQuestionFactory(
        form_page=blank_page,
        question="What is the capital of France?",
        type="multiple_choice",
        order=0,
    )
    QuestionOptionFactory(
        question=blank_question, text="Paris", value="paris", order=0, correct=True
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    _answer(form_progress, answered_question, correct_1, correct_2)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 1, "max_score": 2}
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [blank_question]


@pytest.mark.django_db
def test_compute_quiz_scores_returns_the_figures_without_storing_them(
    mock_site_context,
):
    """The results page re-derives a score to spot a stale one, so computing must not overwrite."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    question, correct_1, correct_2, _wrong_1, _wrong_2 = (
        _build_checkbox_question_two_of_four(form)
    )

    form_progress: FormProgress = FormProgressFactory(
        user=user, form=form, scores={"score": 99, "max_score": 99}
    )
    _answer(form_progress, question, correct_1, correct_2)

    computed = form_progress.compute_quiz_scores()

    assert computed == {"score": 1, "max_score": 1}
    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 99, "max_score": 99}


@pytest.mark.django_db
def test_score_quiz_checkbox_correct_plus_null_correct_option_scores_one(
    mock_site_context,
):
    """A `correct=None` option is neither required nor forbidden — selecting it alongside every
    required option still scores full marks."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="Select all prime numbers",
        type="checkboxes",
        order=0,
    )
    correct_option = QuestionOptionFactory(
        question=question, text="2", value="2", order=0, correct=True
    )
    null_option = QuestionOptionFactory(
        question=question, text="unreviewed", value="3", order=1, correct=None
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    _answer(form_progress, question, correct_option, null_option)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 1
    assert form_progress.get_incorrect_quiz_answers() == []


@pytest.mark.django_db
def test_score_quiz_checkbox_only_null_correct_option_scores_zero(mock_site_context):
    """Selecting only a `correct=None` option, without the required correct option, scores zero."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="Select all prime numbers",
        type="checkboxes",
        order=0,
    )
    QuestionOptionFactory(question=question, text="2", value="2", order=0, correct=True)
    null_option = QuestionOptionFactory(
        question=question, text="unreviewed", value="3", order=1, correct=None
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    _answer(form_progress, question, null_option)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


@pytest.mark.django_db
def test_score_quiz_checkbox_no_correct_option_at_all_scores_zero(mock_site_context):
    """A question with no option marked correct=True can never be answered correctly —
    the regression guard against a naive set-equality rule scoring it correct."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="Unreviewed checkbox question",
        type="checkboxes",
        order=0,
    )
    option_1 = QuestionOptionFactory(
        question=question, text="A", value="1", order=0, correct=False
    )
    option_2 = QuestionOptionFactory(
        question=question, text="B", value="2", order=1, correct=None
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    _answer(form_progress, question, option_1, option_2)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


@pytest.mark.parametrize("question_type", ["short_text", "long_text"])
@pytest.mark.django_db
def test_score_quiz_free_text_question_scores_zero(mock_site_context, question_type):
    """Free-text questions have no options at all, so they can never score correct.

    They are still left out of the incorrect-answer review, which has nothing to
    show for them — see test_quiz_free_text_questions.py.
    """
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="Describe your experience",
        type=question_type,
        order=0,
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    QuestionAnswerFactory(
        form_progress=form_progress, question=question, text_answer="Some free text"
    )

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    assert form_progress.get_incorrect_quiz_answers() == []


@pytest.mark.django_db
def test_score_quiz_with_no_questions_scores_zero_out_of_zero(mock_site_context):
    """A quiz whose questions were added after a learner sat it."""
    form = FormFactory(strategy=FormStrategy.QUIZ)
    FormPageFactory(form=form, title="Empty Page", order=0)
    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 0, "max_score": 0}


@pytest.mark.django_db
def test_quiz_percentage_raises_value_error_when_there_are_no_questions(
    mock_site_context,
):
    form = FormFactory(strategy=FormStrategy.QUIZ)
    FormPageFactory(form=form, title="Empty Page", order=0)
    form_progress: FormProgress = FormProgressFactory(
        user=UserFactory(), form=form, scores={"score": 0, "max_score": 0}
    )

    with pytest.raises(ValueError, match="no questions"):
        form_progress.quiz_percentage()


@pytest.mark.django_db
def test_passed_raises_value_error_when_there_are_no_questions(mock_site_context):
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    FormPageFactory(form=form, title="Empty Page", order=0)
    form_progress: FormProgress = FormProgressFactory(
        user=UserFactory(), form=form, scores={"score": 0, "max_score": 0}
    )

    with pytest.raises(ValueError, match="no questions"):
        form_progress.passed()


@pytest.mark.django_db
def test_quiz_percentage_raises_value_error_when_scores_are_not_quiz_shaped(
    mock_site_context,
):
    """A populated scores dict written under another strategy is not a quiz score.

    Regression: the guard only rejected a falsy scores dict, so a dict with no
    "score" key reached the subscript and raised KeyError, which no caller
    catches. It has to read as an unscored attempt, like every other case here.
    """
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, title="Quiz Page", order=0)
    FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    form_progress: FormProgress = FormProgressFactory(
        user=UserFactory(),
        form=form,
        scores={"Satisfaction": 5, "Recommendation": 3},
    )

    with pytest.raises(ValueError, match="not scored as a quiz"):
        form_progress.quiz_percentage()


@pytest.mark.django_db
def test_passed_raises_value_error_when_scores_are_not_quiz_shaped(mock_site_context):
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    page = FormPageFactory(form=form, title="Quiz Page", order=0)
    FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    form_progress: FormProgress = FormProgressFactory(
        user=UserFactory(),
        form=form,
        scores={"Satisfaction": 5, "Recommendation": 3},
    )

    with pytest.raises(ValueError, match="not scored as a quiz"):
        form_progress.passed()
