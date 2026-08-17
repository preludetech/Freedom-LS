from uuid import uuid4

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.content_engine.models import FormStrategy
from freedom_ls.student_progress.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
)
from freedom_ls.student_progress.models import (
    FormProgress,
    QuestionAnswer,
    evaluate_quiz_answers,
)


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
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(correct_option if select_correct else wrong_option)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == expected_score
    assert form_progress.scores["max_score"] == 1


@pytest.mark.django_db
def test_score_quiz_multiple_questions_mixed_answers(mock_site_context):
    """Test quiz scoring with multiple questions and mixed correct/incorrect answers."""
    user = UserFactory()
    form = FormFactory()

    # Create a page
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)

    # Question 1
    question1 = FormQuestionFactory(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )
    correct_option1 = QuestionOptionFactory(
        question=question1, text="4", value="4", order=0, correct=True
    )
    QuestionOptionFactory(
        question=question1, text="3", value="3", order=1, correct=False
    )

    # Question 2
    question2 = FormQuestionFactory(
        form_page=page,
        question="What is 3 + 3?",
        type="multiple_choice",
        order=1,
    )
    QuestionOptionFactory(
        question=question2, text="6", value="6", order=0, correct=True
    )
    incorrect_option2 = QuestionOptionFactory(
        question=question2, text="5", value="5", order=1, correct=False
    )

    # Question 3
    question3 = FormQuestionFactory(
        form_page=page,
        question="What is 4 + 4?",
        type="multiple_choice",
        order=2,
    )
    correct_option3 = QuestionOptionFactory(
        question=question3, text="8", value="8", order=0, correct=True
    )
    QuestionOptionFactory(
        question=question3, text="7", value="7", order=1, correct=False
    )

    # Create form progress
    form_progress: FormProgress = FormProgressFactory(user=user, form=form)

    # Answer Q1 correctly
    answer1: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question1
    )
    answer1.selected_options.add(correct_option1)

    # Answer Q2 incorrectly
    answer2: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question2
    )
    answer2.selected_options.add(incorrect_option2)

    # Answer Q3 correctly
    answer3: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question3
    )
    answer3.selected_options.add(correct_option3)

    # Call the scoring method
    form_progress.score_quiz()

    # Verify the score: 2 out of 3 correct
    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 2
    assert form_progress.scores["max_score"] == 3


@pytest.mark.django_db
def test_score_quiz_includes_unanswered_questions_in_max_score(
    mock_site_context,
):
    """Test that max_score includes all questions, even unanswered ones."""
    user = UserFactory()
    form = FormFactory()

    # Create a page
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)

    # Question 1
    question1 = FormQuestionFactory(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )
    correct_option1 = QuestionOptionFactory(
        question=question1, text="4", value="4", order=0, correct=True
    )
    QuestionOptionFactory(
        question=question1, text="3", value="3", order=1, correct=False
    )

    # Question 2 (will be unanswered)
    question2 = FormQuestionFactory(
        form_page=page,
        question="What is 3 + 3?",
        type="multiple_choice",
        order=1,
    )
    QuestionOptionFactory(
        question=question2, text="6", value="6", order=0, correct=True
    )
    QuestionOptionFactory(
        question=question2, text="5", value="5", order=1, correct=False
    )

    # Question 3 (will also be unanswered)
    question3 = FormQuestionFactory(
        form_page=page,
        question="What is 4 + 4?",
        type="multiple_choice",
        order=2,
    )
    QuestionOptionFactory(
        question=question3, text="8", value="8", order=0, correct=True
    )
    QuestionOptionFactory(
        question=question3, text="7", value="7", order=1, correct=False
    )

    # Create form progress
    form_progress: FormProgress = FormProgressFactory(user=user, form=form)

    # Answer ONLY question 1 correctly (leave Q2 and Q3 unanswered)
    answer1: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question1
    )
    answer1.selected_options.add(correct_option1)

    # Call the scoring method
    form_progress.score_quiz()

    # Verify the score: 1 out of 3 (max_score should include unanswered questions)
    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 1
    assert form_progress.scores["max_score"] == 3  # All 3 questions count toward max


# Checkbox (multi-select) scoring: exact match, all-or-nothing.


def _build_checkbox_question_two_of_four(form):
    """Checkbox question with 2 correct options of 4, mirroring the qa_helpers fixture shape."""
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="Select all prime numbers",
        type="checkboxes",
        order=0,
    )
    correct_option_1 = QuestionOptionFactory(
        question=question, text="2", value="2", order=0, correct=True
    )
    correct_option_2 = QuestionOptionFactory(
        question=question, text="3", value="3", order=1, correct=True
    )
    wrong_option_1 = QuestionOptionFactory(
        question=question, text="4", value="4", order=2, correct=False
    )
    wrong_option_2 = QuestionOptionFactory(
        question=question, text="6", value="6", order=3, correct=False
    )
    return question, correct_option_1, correct_option_2, wrong_option_1, wrong_option_2


@pytest.mark.django_db
def test_score_quiz_checkbox_exactly_correct_options_scores_one(mock_site_context):
    """Ticking exactly the 2 correct options of 4 scores full marks."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    question, correct_1, correct_2, _wrong_1, _wrong_2 = (
        _build_checkbox_question_two_of_four(form)
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(correct_1, correct_2)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 1
    assert form_progress.scores["max_score"] == 1
    assert form_progress.get_incorrect_quiz_answers() == []


@pytest.mark.django_db
def test_score_quiz_checkbox_ticking_all_four_scores_zero(mock_site_context):
    """The headline bug: ticking every option (2 correct, 2 incorrect) must not score full marks."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    question, correct_1, correct_2, wrong_1, wrong_2 = (
        _build_checkbox_question_two_of_four(form)
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(correct_1, correct_2, wrong_1, wrong_2)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


@pytest.mark.django_db
def test_score_quiz_checkbox_partial_correct_selection_scores_zero(mock_site_context):
    """Ticking only 1 of the 2 correct options scores zero — no partial credit."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    question, correct_1, _correct_2, _wrong_1, _wrong_2 = (
        _build_checkbox_question_two_of_four(form)
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(correct_1)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


@pytest.mark.django_db
def test_score_quiz_checkbox_correct_plus_incorrect_scores_zero(mock_site_context):
    """Ticking both correct options plus one incorrect option scores zero."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    question, correct_1, correct_2, wrong_1, _wrong_2 = (
        _build_checkbox_question_two_of_four(form)
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(correct_1, correct_2, wrong_1)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    incorrect = form_progress.get_incorrect_quiz_answers()
    assert [item["question"] for item in incorrect] == [question]


@pytest.mark.django_db
def test_score_quiz_checkbox_nothing_selected_scores_zero(mock_site_context):
    """A QuestionAnswer exists but has no selected options — scores zero."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    question, _correct_1, _correct_2, _wrong_1, _wrong_2 = (
        _build_checkbox_question_two_of_four(form)
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    QuestionAnswerFactory(form_progress=form_progress, question=question)

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
    assert incorrect[0]["student_selected"] == []


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

    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=FormProgressFactory(user=user, form=form),
        question=answered_question,
    )
    answer.selected_options.add(correct_1, correct_2)
    form_progress = answer.form_progress

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
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(correct_1, correct_2)

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
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(correct_option, null_option)

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
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(null_option)

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
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(option_1, option_2)

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
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.text_answer = "Some free text"
    answer.save()

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0
    assert form_progress.get_incorrect_quiz_answers() == []


# Bulk correctness helper: must classify each (attempt, question) pair identically to score_quiz().


@pytest.mark.django_db
def test_evaluate_quiz_answers_agrees_with_score_quiz_per_question(mock_site_context):
    """evaluate_quiz_answers, fed the same selections score_quiz() saw, must agree question by
    question — not just on the aggregate score."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)

    # Q1: ticks all four (2 correct, 2 incorrect) - should be incorrect.
    question_1 = FormQuestionFactory(
        form_page=page, question="Q1", type="checkboxes", order=0
    )
    q1_correct_1 = QuestionOptionFactory(
        question=question_1, text="A", value="1", order=0, correct=True
    )
    q1_correct_2 = QuestionOptionFactory(
        question=question_1, text="B", value="2", order=1, correct=True
    )
    q1_wrong_1 = QuestionOptionFactory(
        question=question_1, text="C", value="3", order=2, correct=False
    )
    q1_wrong_2 = QuestionOptionFactory(
        question=question_1, text="D", value="4", order=3, correct=False
    )

    # Q2: ticks exactly the correct option - should be correct.
    question_2 = FormQuestionFactory(
        form_page=page, question="Q2", type="checkboxes", order=1
    )
    q2_correct = QuestionOptionFactory(
        question=question_2, text="A", value="1", order=0, correct=True
    )
    q2_wrong = QuestionOptionFactory(
        question=question_2, text="B", value="2", order=1, correct=False
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    answer_1: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question_1
    )
    answer_1.selected_options.add(q1_correct_1, q1_correct_2, q1_wrong_1, q1_wrong_2)
    answer_2: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question_2
    )
    answer_2.selected_options.add(q2_correct)

    form_progress.score_quiz()
    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 1, "max_score": 2}

    options_by_question = {
        question_1.id: [q1_correct_1, q1_correct_2, q1_wrong_1, q1_wrong_2],
        question_2.id: [q2_correct, q2_wrong],
    }
    answer_rows = [
        (
            form_progress.id,
            question_1.id,
            {q1_correct_1.id, q1_correct_2.id, q1_wrong_1.id, q1_wrong_2.id},
        ),
        (form_progress.id, question_2.id, {q2_correct.id}),
    ]

    result = evaluate_quiz_answers(answer_rows, options_by_question)

    assert result == {
        (form_progress.id, question_1.id): False,
        (form_progress.id, question_2.id): True,
    }


@pytest.mark.django_db
def test_evaluate_quiz_answers_issues_no_queries(
    mock_site_context, django_assert_num_queries
):
    """The batched equivalent operates on pre-fetched data only — it must issue no queries."""
    question = FormQuestionFactory(type="checkboxes")
    correct_option = QuestionOptionFactory(question=question, correct=True)
    wrong_option = QuestionOptionFactory(question=question, correct=False)
    options_by_question = {question.id: [correct_option, wrong_option]}
    attempt_id = uuid4()
    answer_rows = [(attempt_id, question.id, {correct_option.id})]

    with django_assert_num_queries(0):
        result = evaluate_quiz_answers(answer_rows, options_by_question)

    assert result == {(attempt_id, question.id): True}


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
