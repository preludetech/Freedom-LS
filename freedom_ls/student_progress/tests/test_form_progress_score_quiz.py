import pytest

from freedom_ls.content_engine.models import FormPage, FormQuestion, QuestionOption
from freedom_ls.student_progress.models import FormProgress, QuestionAnswer


@pytest.mark.django_db
def test_score_quiz_single_correct_answer(mock_site_context, user, form):
    """Test quiz scoring with a single question answered correctly."""

    # Create a page
    page = FormPage.objects.create(form=form, title="Quiz Page 1", order=0)

    # Create a question
    question = FormQuestion.objects.create(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )

    # Create options - one correct, others incorrect
    correct_option = QuestionOption.objects.create(
        question=question, text="4", value="4", order=0, correct=True
    )
    QuestionOption.objects.create(
        question=question, text="3", value="3", order=1, correct=False
    )
    QuestionOption.objects.create(
        question=question, text="5", value="5", order=2, correct=False
    )

    # Create form progress
    form_progress = FormProgress.objects.create(user=user, form=form)

    # Create an answer selecting the correct option
    answer = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(correct_option)

    # Call the scoring method
    form_progress.score_quiz()

    # Verify the score
    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 1
    assert form_progress.scores["max_score"] == 1


@pytest.mark.django_db
def test_score_quiz_single_incorrect_answer(mock_site_context, user, form):
    """Test quiz scoring with a single question answered incorrectly."""

    # Create a page
    page = FormPage.objects.create(form=form, title="Quiz Page 1", order=0)

    # Create a question
    question = FormQuestion.objects.create(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )

    # Create options - one correct, others incorrect
    QuestionOption.objects.create(
        question=question, text="4", value="4", order=0, correct=True
    )
    incorrect_option = QuestionOption.objects.create(
        question=question, text="3", value="3", order=1, correct=False
    )
    QuestionOption.objects.create(
        question=question, text="5", value="5", order=2, correct=False
    )

    # Create form progress
    form_progress = FormProgress.objects.create(user=user, form=form)

    # Create an answer selecting an incorrect option
    answer = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(incorrect_option)

    # Call the scoring method
    form_progress.score_quiz()

    # Verify the score
    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert form_progress.scores["score"] == 0  # Got it wrong
    assert form_progress.scores["max_score"] == 1


@pytest.mark.django_db
def test_score_quiz_multiple_questions_mixed_answers(mock_site_context, user, form):
    """Test quiz scoring with multiple questions and mixed correct/incorrect answers."""

    # Create a page
    page = FormPage.objects.create(form=form, title="Quiz Page 1", order=0)

    # Question 1
    question1 = FormQuestion.objects.create(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )
    correct_option1 = QuestionOption.objects.create(
        question=question1, text="4", value="4", order=0, correct=True
    )
    QuestionOption.objects.create(
        question=question1, text="3", value="3", order=1, correct=False
    )

    # Question 2
    question2 = FormQuestion.objects.create(
        form_page=page,
        question="What is 3 + 3?",
        type="multiple_choice",
        order=1,
    )
    QuestionOption.objects.create(
        question=question2, text="6", value="6", order=0, correct=True
    )
    incorrect_option2 = QuestionOption.objects.create(
        question=question2, text="5", value="5", order=1, correct=False
    )

    # Question 3
    question3 = FormQuestion.objects.create(
        form_page=page,
        question="What is 4 + 4?",
        type="multiple_choice",
        order=2,
    )
    correct_option3 = QuestionOption.objects.create(
        question=question3, text="8", value="8", order=0, correct=True
    )
    QuestionOption.objects.create(
        question=question3, text="7", value="7", order=1, correct=False
    )

    # Create form progress
    form_progress = FormProgress.objects.create(user=user, form=form)

    # Answer Q1 correctly
    answer1 = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question1
    )
    answer1.selected_options.add(correct_option1)

    # Answer Q2 incorrectly
    answer2 = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question2
    )
    answer2.selected_options.add(incorrect_option2)

    # Answer Q3 correctly
    answer3 = QuestionAnswer.objects.create(
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
    mock_site_context, user, form
):
    """Test that max_score includes all questions, even unanswered ones."""

    # Create a page
    page = FormPage.objects.create(form=form, title="Quiz Page 1", order=0)

    # Question 1
    question1 = FormQuestion.objects.create(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )
    correct_option1 = QuestionOption.objects.create(
        question=question1, text="4", value="4", order=0, correct=True
    )
    QuestionOption.objects.create(
        question=question1, text="3", value="3", order=1, correct=False
    )

    # Question 2 (will be unanswered)
    question2 = FormQuestion.objects.create(
        form_page=page,
        question="What is 3 + 3?",
        type="multiple_choice",
        order=1,
    )
    QuestionOption.objects.create(
        question=question2, text="6", value="6", order=0, correct=True
    )
    QuestionOption.objects.create(
        question=question2, text="5", value="5", order=1, correct=False
    )

    # Question 3 (will also be unanswered)
    question3 = FormQuestion.objects.create(
        form_page=page,
        question="What is 4 + 4?",
        type="multiple_choice",
        order=2,
    )
    QuestionOption.objects.create(
        question=question3, text="8", value="8", order=0, correct=True
    )
    QuestionOption.objects.create(
        question=question3, text="7", value="7", order=1, correct=False
    )

    # Create form progress
    form_progress = FormProgress.objects.create(user=user, form=form)

    # Answer ONLY question 1 correctly (leave Q2 and Q3 unanswered)
    answer1 = QuestionAnswer.objects.create(
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
