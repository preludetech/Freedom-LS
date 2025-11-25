import pytest

from content_engine.models import FormPage, FormQuestion, QuestionOption
from student_progress.models import FormProgress, QuestionAnswer


@pytest.mark.django_db
def test_score_category_value_sum_single_question(mock_site_context, user, form):
    """Test score_category_value_sum with a single question and answer."""

    # Create a page with a category
    page = FormPage.objects.create(
        form=form, title="Page 1", order=0, category="Wellbeing"
    )

    # Create a question with a category
    question = FormQuestion.objects.create(
        form_page=page,
        question="How are you feeling?",
        type="multiple_choice",
        order=0,
        category="Mental Health",
    )

    # Create options with values
    option1 = QuestionOption.objects.create(
        question=question, text="Great", value="5", order=0
    )
    QuestionOption.objects.create(question=question, text="Good", value="3", order=1)
    QuestionOption.objects.create(question=question, text="Poor", value="1", order=2)

    # Create form progress
    form_progress = FormProgress.objects.create(user=user, form=form)

    # Create an answer selecting option1 (value=5)
    answer = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(option1)

    # Call the scoring method
    form_progress.score_category_value_sum()

    # Verify the scores
    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert "Wellbeing" in form_progress.scores
    assert form_progress.scores["Wellbeing"]["score"] == 5
    assert form_progress.scores["Wellbeing"]["max_score"] == 5
    assert "Mental Health" in form_progress.scores["Wellbeing"]["sub_categories"]
    assert (
        form_progress.scores["Wellbeing"]["sub_categories"]["Mental Health"]["score"]
        == 5
    )
    assert (
        form_progress.scores["Wellbeing"]["sub_categories"]["Mental Health"][
            "max_score"
        ]
        == 5
    )


@pytest.mark.django_db
def test_score_category_value_sum_calculates_max_score_correctly_with_unanswered_questions(
    mock_site_context, user, form
):
    """Test that max score includes all questions, even unanswered ones."""

    # Create a page with a category
    page = FormPage.objects.create(
        form=form, title="Page 1", order=0, category="Wellbeing"
    )

    # Create 2 questions in the same category
    question1 = FormQuestion.objects.create(
        form_page=page,
        question="Question 1",
        type="multiple_choice",
        order=0,
        category="Mental Health",
    )

    question2 = FormQuestion.objects.create(
        form_page=page,
        question="Question 2",
        type="multiple_choice",
        order=1,
        category="Mental Health",
    )

    # Create options for question 1 (max value = 5)
    option1_q1 = QuestionOption.objects.create(
        question=question1, text="Option 1", value="5", order=0
    )
    QuestionOption.objects.create(
        question=question1, text="Option 2", value="3", order=1
    )

    # Create options for question 2 (max value = 10)
    QuestionOption.objects.create(
        question=question2, text="Option 1", value="10", order=0
    )
    QuestionOption.objects.create(
        question=question2, text="Option 2", value="7", order=1
    )

    # Create form progress
    form_progress = FormProgress.objects.create(user=user, form=form)

    # Answer ONLY question 1 (leave question 2 unanswered)
    answer1 = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question1
    )
    answer1.selected_options.add(option1_q1)

    # Call the scoring method
    form_progress.score_category_value_sum()

    # Verify the scores
    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert "Wellbeing" in form_progress.scores

    # The actual score should be 5 (only Q1 answered)
    assert form_progress.scores["Wellbeing"]["score"] == 5

    # The max score should be 5 + 10 = 15 (both questions counted)
    # This will FAIL because the current implementation only counts answered questions
    assert form_progress.scores["Wellbeing"]["max_score"] == 15


@pytest.mark.django_db
def test_score_category_value_sum_categorises_questions_correctly(
    mock_site_context, user, form
):
    """Test that questions without subcategories don't create 'Uncategorized' subcategories."""

    # Create a page with a category
    page = FormPage.objects.create(
        form=form, title="Anatomy Page", order=0, category="Anatomy"
    )

    # Create a question WITHOUT a subcategory (should be top-level)
    question1 = FormQuestion.objects.create(
        form_page=page,
        question="Question without subcategory",
        type="multiple_choice",
        order=0,
        category=None,  # No subcategory
    )

    # Create a question WITH a subcategory
    question2 = FormQuestion.objects.create(
        form_page=page,
        question="Question with subcategory",
        type="multiple_choice",
        order=1,
        category="Bones",  # Has subcategory
    )

    # Create options for question 1 (max value = 5)
    option1_q1 = QuestionOption.objects.create(
        question=question1, text="Option 1", value="5", order=0
    )
    QuestionOption.objects.create(
        question=question1, text="Option 2", value="3", order=1
    )

    # Create options for question 2 (max value = 10)
    option1_q2 = QuestionOption.objects.create(
        question=question2, text="Option 1", value="10", order=0
    )
    QuestionOption.objects.create(
        question=question2, text="Option 2", value="7", order=1
    )

    # Create form progress
    form_progress = FormProgress.objects.create(user=user, form=form)

    # Answer both questions
    answer1 = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question1
    )
    answer1.selected_options.add(option1_q1)

    answer2 = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question2
    )
    answer2.selected_options.add(option1_q2)

    # Call the scoring method
    form_progress.score_category_value_sum()

    # Verify the scores
    form_progress.refresh_from_db()
    assert form_progress.scores is not None
    assert "Anatomy" in form_progress.scores

    # Parent category should have combined scores (5 + 10 = 15)
    assert form_progress.scores["Anatomy"]["score"] == 15
    assert form_progress.scores["Anatomy"]["max_score"] == 15

    # Should NOT have "Uncategorized" in subcategories
    assert "Uncategorized" not in form_progress.scores["Anatomy"]["sub_categories"]

    # Should only have "Bones" subcategory (for question2)
    assert "Bones" in form_progress.scores["Anatomy"]["sub_categories"]
    assert form_progress.scores["Anatomy"]["sub_categories"]["Bones"]["score"] == 10
    assert form_progress.scores["Anatomy"]["sub_categories"]["Bones"]["max_score"] == 10

    # Question1 (without subcategory) should contribute to parent but not create a subcategory
    # So we should only have 1 subcategory, not 2
    assert len(form_progress.scores["Anatomy"]["sub_categories"]) == 1


@pytest.mark.django_db
def test_score_category_value_sum_with_three_level_hierarchy(
    mock_site_context, user, form
):
    """Test that nested categories with pipe separator create 3-level hierarchy."""

    # Create a page with nested categories using pipe separator
    page = FormPage.objects.create(
        form=form, title="Health Page", order=0, category="Wellbeing | Physical Health"
    )

    # Create a question with its own category (creates 3rd level)
    question1 = FormQuestion.objects.create(
        form_page=page,
        question="How often do you exercise?",
        type="multiple_choice",
        order=0,
        category="Exercise",
    )

    # Create another question in the same page but different bottom-level category
    question2 = FormQuestion.objects.create(
        form_page=page,
        question="What's your diet like?",
        type="multiple_choice",
        order=1,
        category="Nutrition",
    )

    # Create options for question 1 (max value = 5)
    option1_q1 = QuestionOption.objects.create(
        question=question1, text="Daily", value="5", order=0
    )
    QuestionOption.objects.create(
        question=question1, text="Weekly", value="3", order=1
    )

    # Create options for question 2 (max value = 10)
    option1_q2 = QuestionOption.objects.create(
        question=question2, text="Excellent", value="10", order=0
    )
    QuestionOption.objects.create(
        question=question2, text="Good", value="7", order=1
    )

    # Create form progress
    form_progress = FormProgress.objects.create(user=user, form=form)

    # Answer both questions
    answer1 = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question1
    )
    answer1.selected_options.add(option1_q1)

    answer2 = QuestionAnswer.objects.create(
        form_progress=form_progress, question=question2
    )
    answer2.selected_options.add(option1_q2)

    # Call the scoring method
    form_progress.score_category_value_sum()

    # Verify the 3-level structure
    form_progress.refresh_from_db()
    assert form_progress.scores is not None

    # Level 1: "Wellbeing" (top level from pipe-separated category)
    assert "Wellbeing" in form_progress.scores
    assert form_progress.scores["Wellbeing"]["score"] == 15  # 5 + 10
    assert form_progress.scores["Wellbeing"]["max_score"] == 15

    # Level 2: "Physical Health" (middle level from pipe-separated category)
    assert "Physical Health" in form_progress.scores["Wellbeing"]["sub_categories"]
    assert (
        form_progress.scores["Wellbeing"]["sub_categories"]["Physical Health"]["score"]
        == 15
    )
    assert (
        form_progress.scores["Wellbeing"]["sub_categories"]["Physical Health"][
            "max_score"
        ]
        == 15
    )

    # Level 3: "Exercise" and "Nutrition" (bottom level from question categories)
    physical_health_subs = form_progress.scores["Wellbeing"]["sub_categories"][
        "Physical Health"
    ]["sub_categories"]

    assert "Exercise" in physical_health_subs
    assert physical_health_subs["Exercise"]["score"] == 5
    assert physical_health_subs["Exercise"]["max_score"] == 5

    assert "Nutrition" in physical_health_subs
    assert physical_health_subs["Nutrition"]["score"] == 10
    assert physical_health_subs["Nutrition"]["max_score"] == 10
